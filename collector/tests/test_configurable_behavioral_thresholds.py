"""Tests for configurable behavioral thresholds (Priority 1).

Validates:
- Server-pushed config overrides file-based defaults
- Custom LLM hosts are unioned with (not replacing) defaults
- Default behavior unchanged when no config override is provided
- Heartbeat response includes behavioral_config when profile has one
- Running multiple scans does not accumulate LLM hosts (the old bug)
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from scanner.behavioral import BehavioralScanner, _flatten_thresholds, _load_behavioral_config
from scanner.behavioral_patterns import (
    _DEFAULT_LLM_HOSTS,
    _LLM_API_HOSTS,
    detect_all_patterns,
    detect_llm_cadence,
    detect_shell_fanout,
    get_default_llm_hosts,
    get_llm_hosts,
)
from scanner.process_tree import ProcessNode
from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

_BASE = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)


def _make_tree(
    pid: int = 100,
    ppid: int = 0,
    name: str = "python3",
    cmdline: str = "python3 agent.py",
    children: list[ProcessNode] | None = None,
    network_events: list[NetworkConnectEvent] | None = None,
    file_events: list[FileChangeEvent] | None = None,
    start_time: datetime | None = None,
) -> ProcessNode:
    return ProcessNode(
        pid=pid,
        ppid=ppid,
        name=name,
        cmdline=cmdline,
        children=children or [],
        network_events=network_events or [],
        file_events=file_events or [],
        start_time=start_time or _BASE,
    )


class TestBehavioralConfigOverrideApplied(unittest.TestCase):
    """Verify server-pushed thresholds override file defaults."""

    def test_shell_fanout_threshold_override(self) -> None:
        """With higher min_children threshold, fewer shells should NOT trigger."""
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i),
            )
            for i in range(7)
        ]
        root = _make_tree(pid=100, ppid=0, children=shells, start_time=_BASE)

        # Default threshold is 5, so 7 shells should trigger
        match_default = detect_shell_fanout(root)
        self.assertGreater(match_default.score, 0.0)

        # Override to require 10 -- 7 shells should NOT trigger now
        overridden_thresholds = {"shell_fanout_min_children": 10}
        match_overridden = detect_shell_fanout(root, thresholds=overridden_thresholds)
        self.assertEqual(match_overridden.score, 0.0)

    def test_shell_fanout_window_override(self) -> None:
        """With a shorter window, shells spread over time should NOT trigger."""
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i * 15),  # 15s apart
            )
            for i in range(6)
        ]
        root = _make_tree(pid=100, ppid=0, children=shells, start_time=_BASE)

        # Default window is 60s; shells span 0-75s. In any 60s window, at most 5.
        # With window=30s, max in window is 3 which is below default min_children=5.
        overridden = {"shell_fanout_window_seconds": 30, "shell_fanout_min_children": 5}
        match = detect_shell_fanout(root, thresholds=overridden)
        self.assertEqual(match.score, 0.0)

    def test_scanner_config_override_merges(self) -> None:
        """BehavioralScanner with config_override merges on top of file defaults."""
        store = EventStore(max_events=1000, retention_seconds=86400 * 365)
        store.push_process(
            ProcessExecEvent(
                timestamp=_BASE,
                pid=100,
                ppid=0,
                name="python3",
                cmdline="python3 agent.py",
            )
        )
        for i in range(7):
            store.push_process(
                ProcessExecEvent(
                    timestamp=_BASE + timedelta(seconds=i),
                    pid=101 + i,
                    ppid=100,
                    name="bash",
                    cmdline="bash",
                )
            )

        # Without override: default min_children=5, so 7 shells should detect
        scanner_default = BehavioralScanner(event_store=store)
        result_default = scanner_default.scan()

        # With override raising threshold: 7 shells < 15, should NOT detect
        scanner_override = BehavioralScanner(
            event_store=store,
            config_override={"BEH-001": {"shell_fanout_min_children": 15}},
        )
        result_override = scanner_override.scan()

        # The override scanner should not detect (or at least have fewer matches).
        # Note: detection depends on aggregate score; the key point is the threshold
        # change propagates to the pattern detector.
        self.assertFalse(result_override.detected)

    def test_detect_all_patterns_uses_overridden_thresholds(self) -> None:
        """detect_all_patterns passes thresholds through to each detector."""
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i),
            )
            for i in range(7)
        ]
        root = _make_tree(pid=100, ppid=0, children=shells, start_time=_BASE)

        # Default: min_children=5, should match
        matches_default = detect_all_patterns(root)
        beh001_default = [m for m in matches_default if m.pattern_id == "BEH-001"]
        self.assertEqual(len(beh001_default), 1)

        # Override: min_children=10, should NOT match
        matches_override = detect_all_patterns(
            root, thresholds={"shell_fanout_min_children": 10}
        )
        beh001_override = [m for m in matches_override if m.pattern_id == "BEH-001"]
        self.assertEqual(len(beh001_override), 0)


class TestCustomLLMHostsMerged(unittest.TestCase):
    """Verify custom hosts are unioned with defaults, not replacing them."""

    def test_custom_hosts_union_not_replace(self) -> None:
        """Custom LLM hosts should be added to defaults, not replace them."""
        custom_hosts = {"vllm.internal:8000", "tgi.corp.net:443"}
        combined = set(_DEFAULT_LLM_HOSTS) | custom_hosts

        # Pass custom hosts as llm_hosts parameter
        net_events = [
            NetworkConnectEvent(
                timestamp=_BASE,
                pid=100,
                process_name="python3",
                remote_addr="vllm.internal",
                remote_port=8000,
                local_port=5000,
            ),
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=1),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5001,
            ),
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=2),
                pid=100,
                process_name="python3",
                remote_addr="tgi.corp.net",
                remote_port=443,
                local_port=5002,
            ),
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net_events, start_time=_BASE)

        match = detect_llm_cadence(root, llm_hosts=combined)
        self.assertGreater(match.score, 0.0)
        # All three hosts should be recognized as LLM
        self.assertEqual(match.evidence["llm_connections_in_window"], 3)

    def test_default_hosts_still_work_with_custom(self) -> None:
        """Default hosts like api.openai.com must still be recognized when custom hosts are added."""
        custom_hosts = {"vllm.internal:8000"}
        combined = set(_DEFAULT_LLM_HOSTS) | custom_hosts

        net_events = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000 + i,
            )
            for i in range(3)
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net_events, start_time=_BASE)

        match = detect_llm_cadence(root, llm_hosts=combined)
        self.assertGreater(match.score, 0.0)

    def test_scanner_merges_custom_llm_hosts_from_config_override(self) -> None:
        """BehavioralScanner with config_override containing custom_llm_hosts merges correctly."""
        scanner = BehavioralScanner(
            event_store=EventStore(max_events=100, retention_seconds=60),
            config_override={"custom_llm_hosts": ["vllm.internal:8000"]},
        )
        # The scanner's instance-level hosts should contain both defaults and custom
        self.assertIn("api.openai.com", scanner._llm_hosts)
        self.assertIn("vllm.internal:8000", scanner._llm_hosts)
        self.assertIn("api.anthropic.com", scanner._llm_hosts)


class TestDefaultBehaviorUnchanged(unittest.TestCase):
    """Verify that with no config override, behavior is identical to current."""

    def test_no_override_uses_file_defaults(self) -> None:
        """BehavioralScanner without config_override loads file-based config only."""
        scanner = BehavioralScanner(
            event_store=EventStore(max_events=100, retention_seconds=60),
        )
        # Should have loaded file-based config (or empty dict if file doesn't exist)
        # The key assertion is that no override was applied
        self.assertIsNotNone(scanner._config)
        self.assertIsNotNone(scanner._thresholds)

    def test_detect_all_patterns_backward_compatible(self) -> None:
        """detect_all_patterns with no llm_hosts param behaves identically to old code."""
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i),
            )
            for i in range(6)
        ]
        root = _make_tree(pid=100, ppid=0, children=shells, start_time=_BASE)

        # Call without llm_hosts (backward-compatible signature)
        matches = detect_all_patterns(root)
        beh001 = [m for m in matches if m.pattern_id == "BEH-001"]
        self.assertEqual(len(beh001), 1)

    def test_detect_shell_fanout_no_kwargs(self) -> None:
        """detect_shell_fanout still works with old 3-arg calling convention."""
        shells = [
            _make_tree(
                pid=101 + i,
                ppid=100,
                name="bash",
                start_time=_BASE + timedelta(seconds=i),
            )
            for i in range(6)
        ]
        root = _make_tree(pid=100, ppid=0, children=shells, start_time=_BASE)

        # Old-style call: positional args only
        match = detect_shell_fanout(root, None, None)
        self.assertGreater(match.score, 0.0)

    def test_detect_llm_cadence_no_kwargs(self) -> None:
        """detect_llm_cadence still works with old 3-arg calling convention."""
        net_events = [
            NetworkConnectEvent(
                timestamp=_BASE + timedelta(seconds=i),
                pid=100,
                process_name="python3",
                remote_addr="api.openai.com",
                remote_port=443,
                local_port=5000 + i,
            )
            for i in range(4)
        ]
        root = _make_tree(pid=100, ppid=0, network_events=net_events, start_time=_BASE)

        # Old-style call: positional args only, no llm_hosts kwarg
        match = detect_llm_cadence(root, None, None)
        self.assertGreater(match.score, 0.0)

    def test_get_default_llm_hosts_returns_frozenset(self) -> None:
        """get_default_llm_hosts returns immutable frozenset with known hosts."""
        defaults = get_default_llm_hosts()
        self.assertIsInstance(defaults, frozenset)
        self.assertIn("api.openai.com", defaults)
        self.assertIn("api.anthropic.com", defaults)


class TestHeartbeatIncludesBehavioralConfig(unittest.TestCase):
    """Verify heartbeat response includes config when profile has it.

    This is an integration-level concern; we test the data flow at the
    schema level since running the full API requires database fixtures.
    """

    def test_heartbeat_response_schema_accepts_behavioral_config(self) -> None:
        """HeartbeatResponse model accepts behavioral_config field."""
        # Import here to avoid import-time DB connection issues
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
        try:
            from routers.endpoints import HeartbeatResponse
        except ImportError:
            self.skipTest("API module not importable from collector test environment")

        resp = HeartbeatResponse(
            status="ok",
            endpoint_id="ep-1",
            endpoint_status="active",
            next_expected_in=300,
            behavioral_config={
                "shell_fanout_min_children": 10,
                "custom_llm_hosts": ["vllm.internal:8000"],
            },
        )
        self.assertEqual(resp.behavioral_config["shell_fanout_min_children"], 10)
        self.assertIn("vllm.internal:8000", resp.behavioral_config["custom_llm_hosts"])

    def test_heartbeat_response_schema_none_when_absent(self) -> None:
        """HeartbeatResponse with no behavioral_config defaults to None."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))
        try:
            from routers.endpoints import HeartbeatResponse
        except ImportError:
            self.skipTest("API module not importable from collector test environment")

        resp = HeartbeatResponse(
            status="ok",
            endpoint_id="ep-1",
            endpoint_status="active",
            next_expected_in=300,
        )
        self.assertIsNone(resp.behavioral_config)


class TestLLMHostsNotAccumulated(unittest.TestCase):
    """Verify that running multiple scans doesn't accumulate hosts (the old bug)."""

    def test_instance_level_hosts_do_not_leak(self) -> None:
        """Each BehavioralScanner instance gets its own hosts set."""
        store = EventStore(max_events=100, retention_seconds=60)

        scanner1 = BehavioralScanner(
            event_store=store,
            config_override={"custom_llm_hosts": ["scan1.internal:8000"]},
        )
        scanner2 = BehavioralScanner(
            event_store=store,
            config_override={"custom_llm_hosts": ["scan2.internal:9000"]},
        )

        # scanner1 should have scan1 host but NOT scan2
        self.assertIn("scan1.internal:8000", scanner1._llm_hosts)
        # scanner2 should have scan2 host
        self.assertIn("scan2.internal:9000", scanner2._llm_hosts)

        # Each scanner's instance hosts should NOT contain the other's custom host
        # (unless it was added to the global set by a previous scanner).
        # The key design: instance hosts are built from defaults + own config only.
        # scanner1 was created BEFORE scanner2, so scanner1._llm_hosts
        # should not contain scan2's host.
        self.assertNotIn("scan2.internal:9000", scanner1._llm_hosts)

    def test_default_hosts_immutable(self) -> None:
        """_DEFAULT_LLM_HOSTS should be a frozenset that never changes."""
        original = frozenset(_DEFAULT_LLM_HOSTS)
        # Create scanners with different custom hosts
        store = EventStore(max_events=100, retention_seconds=60)
        BehavioralScanner(
            event_store=store,
            config_override={"custom_llm_hosts": ["x.internal:8000"]},
        )
        # Default hosts should be unchanged
        self.assertEqual(_DEFAULT_LLM_HOSTS, original)
        self.assertNotIn("x.internal:8000", _DEFAULT_LLM_HOSTS)

    def test_detect_all_patterns_with_explicit_hosts_no_side_effect(self) -> None:
        """Passing llm_hosts to detect_all_patterns should not change module state."""
        custom = set(_DEFAULT_LLM_HOSTS) | {"ephemeral.host:1234"}
        root = _make_tree(pid=100, ppid=0, start_time=_BASE)

        detect_all_patterns(root, llm_hosts=custom)

        # The module-level _DEFAULT_LLM_HOSTS should NOT contain the custom host
        self.assertNotIn("ephemeral.host:1234", _DEFAULT_LLM_HOSTS)

    def test_flatten_thresholds_handles_override_config(self) -> None:
        """_flatten_thresholds correctly processes overridden config dicts."""
        config = {
            "BEH-001": {"shell_fanout_min_children": 15, "shell_fanout_window_seconds": 120},
            "BEH-002": {"llm_cadence_min_connections": 10},
            "custom_llm_hosts": ["vllm.internal:8000"],
            "detection_threshold": 0.5,
        }
        flat = _flatten_thresholds(config)
        self.assertEqual(flat["shell_fanout_min_children"], 15)
        self.assertEqual(flat["shell_fanout_window_seconds"], 120)
        self.assertEqual(flat["llm_cadence_min_connections"], 10)
        self.assertEqual(flat["detection_threshold"], 0.5)
        # custom_llm_hosts is a list, not a nested dict, so should appear as-is
        self.assertEqual(flat["custom_llm_hosts"], ["vllm.internal:8000"])


if __name__ == "__main__":
    unittest.main()
