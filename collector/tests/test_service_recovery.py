"""Tests for Task 11b: DisabledServiceTracker and service_restore lifecycle.

Covers the anti-resurrection recovery path: tracking disabled services,
persisting state across restarts, restoring by ID, and the platform-specific
restore functions (systemd, launchd) with mocked subprocess calls.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.state import DisabledService, DisabledServiceTracker


# ---------------------------------------------------------------------------
# DisabledServiceTracker unit tests
# ---------------------------------------------------------------------------

class TestDisabledServiceTracker:
    def test_empty_on_init(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        assert tracker.get_disabled_services() == []
        assert tracker.to_heartbeat_payload() == []

    def test_add_and_retrieve_service(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="svc-1",
            service_type="systemd",
            unit_name="rogue-agent.service",
            tool_name="RogueBot",
        )
        tracker.add_service(svc)
        services = tracker.get_disabled_services()
        assert len(services) == 1
        assert services[0].service_id == "svc-1"
        assert services[0].unit_name == "rogue-agent.service"
        assert services[0].disabled_at > 0

    def test_add_preserves_explicit_timestamp(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        ts = 1700000000.0
        svc = DisabledService(
            service_id="svc-ts",
            service_type="launchd",
            unit_name="com.rogue.agent",
            plist_path="/Library/LaunchDaemons/com.rogue.agent.plist",
            disabled_at=ts,
        )
        tracker.add_service(svc)
        assert tracker.get_service("svc-ts").disabled_at == ts

    def test_remove_service(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        tracker.add_service(DisabledService(
            service_id="svc-rm",
            service_type="systemd",
            unit_name="bad.service",
        ))
        assert len(tracker.get_disabled_services()) == 1
        tracker.remove_service("svc-rm")
        assert tracker.get_disabled_services() == []

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        tracker.remove_service("does-not-exist")
        assert tracker.get_disabled_services() == []

    def test_get_service_returns_none_for_missing(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        assert tracker.get_service("nope") is None

    def test_clear_all(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        for i in range(3):
            tracker.add_service(DisabledService(
                service_id=f"svc-{i}",
                service_type="systemd",
                unit_name=f"unit-{i}.service",
            ))
        assert len(tracker.get_disabled_services()) == 3
        tracker.clear_all()
        assert tracker.get_disabled_services() == []

    def test_persistence_across_restart(self, tmp_path: Path) -> None:
        tracker1 = DisabledServiceTracker(state_dir=tmp_path)
        tracker1.add_service(DisabledService(
            service_id="persist-1",
            service_type="launchd",
            unit_name="com.persist.agent",
            plist_path="/Library/LaunchDaemons/com.persist.agent.plist",
            tool_name="PersistBot",
        ))
        del tracker1

        tracker2 = DisabledServiceTracker(state_dir=tmp_path)
        services = tracker2.get_disabled_services()
        assert len(services) == 1
        assert services[0].service_id == "persist-1"
        assert services[0].tool_name == "PersistBot"

    def test_corrupted_state_file_recovers(self, tmp_path: Path) -> None:
        state_path = tmp_path / "disabled_services.json"
        state_path.write_text("NOT VALID JSON {{{", encoding="utf-8")
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        assert tracker.get_disabled_services() == []

    def test_malformed_entry_skipped(self, tmp_path: Path) -> None:
        state_path = tmp_path / "disabled_services.json"
        state_path.write_text(json.dumps({
            "good": {
                "service_id": "good",
                "service_type": "systemd",
                "unit_name": "good.service",
            },
            "bad": {"garbage_key": True},
        }), encoding="utf-8")
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        services = tracker.get_disabled_services()
        assert len(services) == 1
        assert services[0].service_id == "good"

    def test_to_heartbeat_payload_format(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        tracker.add_service(DisabledService(
            service_id="hb-1",
            service_type="systemd",
            unit_name="test.service",
            tool_name="TestTool",
            disabled_at=1700000000.0,
        ))
        payload = tracker.to_heartbeat_payload()
        assert len(payload) == 1
        assert isinstance(payload[0], dict)
        assert payload[0]["service_id"] == "hb-1"
        assert payload[0]["service_type"] == "systemd"
        assert payload[0]["unit_name"] == "test.service"
        assert payload[0]["tool_name"] == "TestTool"
        assert payload[0]["disabled_at"] == 1700000000.0

    def test_multiple_services_tracked(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        tracker.add_service(DisabledService(
            service_id="a", service_type="systemd", unit_name="a.service",
        ))
        tracker.add_service(DisabledService(
            service_id="b", service_type="launchd", unit_name="com.b.agent",
            plist_path="/Library/LaunchDaemons/com.b.agent.plist",
        ))
        services = tracker.get_disabled_services()
        ids = {s.service_id for s in services}
        assert ids == {"a", "b"}

    def test_add_same_id_overwrites(self, tmp_path: Path) -> None:
        tracker = DisabledServiceTracker(state_dir=tmp_path)
        tracker.add_service(DisabledService(
            service_id="dup",
            service_type="systemd",
            unit_name="old.service",
            disabled_at=100.0,
        ))
        tracker.add_service(DisabledService(
            service_id="dup",
            service_type="systemd",
            unit_name="new.service",
            disabled_at=200.0,
        ))
        services = tracker.get_disabled_services()
        assert len(services) == 1
        assert services[0].unit_name == "new.service"


# ---------------------------------------------------------------------------
# service_restore tests
# ---------------------------------------------------------------------------

class TestServiceRestore:
    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_systemd_success(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.return_value = MagicMock(returncode=0, stderr="")

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="sys-1",
            service_type="systemd",
            unit_name="rogue.service",
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is True
        mock_subprocess.run.assert_called_once_with(
            ["systemctl", "enable", "--now", "rogue.service"],
            capture_output=True, text=True, timeout=10,
        )
        assert tracker.get_service("sys-1") is None

    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_systemd_failure_keeps_in_tracker(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.return_value = MagicMock(returncode=1, stderr="unit not found")

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="sys-fail",
            service_type="systemd",
            unit_name="missing.service",
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is False
        assert tracker.get_service("sys-fail") is not None

    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_launchd_success(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Darwin"
        mock_subprocess.run.return_value = MagicMock(returncode=0, stderr="")

        plist = tmp_path / "com.rogue.plist"
        plist.write_text("<plist/>", encoding="utf-8")

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="ld-1",
            service_type="launchd",
            unit_name="com.rogue.agent",
            plist_path=str(plist),
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is True
        mock_subprocess.run.assert_called_once_with(
            ["launchctl", "load", "-w", str(plist)],
            capture_output=True, text=True, timeout=10,
        )
        assert tracker.get_service("ld-1") is None

    @patch("enforcement.service_restore.platform")
    def test_restore_launchd_missing_plist_returns_false(self, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Darwin"

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="ld-missing",
            service_type="launchd",
            unit_name="com.gone.agent",
            plist_path="/nonexistent/path.plist",
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is False

    @patch("enforcement.service_restore.platform")
    def test_restore_wrong_platform_removes_from_tracker(self, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Windows"

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="cross-plat",
            service_type="systemd",
            unit_name="linux-only.service",
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is False
        # Unsupported platform removes from tracker to avoid repeated failures
        assert tracker.get_service("cross-plat") is None

    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_systemd_timeout(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        import subprocess as real_subprocess
        from enforcement.service_restore import restore_service

        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.side_effect = real_subprocess.TimeoutExpired(cmd="systemctl", timeout=10)
        mock_subprocess.TimeoutExpired = real_subprocess.TimeoutExpired

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        svc = DisabledService(
            service_id="sys-timeout",
            service_type="systemd",
            unit_name="slow.service",
            disabled_at=time.time(),
        )
        tracker.add_service(svc)

        result = restore_service(svc, tracker)
        assert result is False
        assert tracker.get_service("sys-timeout") is not None


class TestRestoreByIds:
    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_specific_ids(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_by_ids

        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.return_value = MagicMock(returncode=0, stderr="")

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        for i in range(3):
            tracker.add_service(DisabledService(
                service_id=f"svc-{i}",
                service_type="systemd",
                unit_name=f"unit-{i}.service",
                disabled_at=time.time(),
            ))

        results = restore_by_ids(["svc-0", "svc-2"], tracker)
        assert results == {"svc-0": True, "svc-2": True}
        assert tracker.get_service("svc-0") is None
        assert tracker.get_service("svc-1") is not None
        assert tracker.get_service("svc-2") is None

    def test_restore_unknown_id_returns_false(self, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_by_ids

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        results = restore_by_ids(["nonexistent"], tracker)
        assert results == {"nonexistent": False}

    @patch("enforcement.service_restore.platform")
    @patch("enforcement.service_restore.subprocess")
    def test_restore_all(self, mock_subprocess, mock_platform, tmp_path: Path) -> None:
        from enforcement.service_restore import restore_all

        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.return_value = MagicMock(returncode=0, stderr="")

        tracker = DisabledServiceTracker(state_dir=tmp_path)
        for i in range(2):
            tracker.add_service(DisabledService(
                service_id=f"all-{i}",
                service_type="systemd",
                unit_name=f"unit-{i}.service",
                disabled_at=time.time(),
            ))

        results = restore_all(tracker)
        assert all(v is True for v in results.values())
        assert len(results) == 2
        assert tracker.get_disabled_services() == []
