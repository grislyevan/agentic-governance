"""Tests for cgroup v2 network blocking and cleanup.

Covers:
  - _cgroup_v2_block: success path, net_cls unavailable fallback, iptables failure rollback
  - _cgroup_v2_unblock: removes iptables rule and cgroup dir
  - _block_linux: cgroup path vs UID-owner fallback
  - _unblock_linux: cgroup unblock before UID-owner fallback
  - _cleanup_linux_cgroups: stale cgroup directory removal
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

from enforcement.network_block import (
    CGROUP_BASE,
    CGROUP_DIR_PREFIX,
    _classid_for_pid,
    _cgroup_v2_available,
    _cgroup_v2_block,
    _cgroup_v2_unblock,
    _remove_cgroup,
    _block_linux,
    _unblock_linux,
)
from enforcement.cleanup import _cleanup_linux_cgroups


class TestClassidForPid:
    def test_deterministic(self) -> None:
        assert _classid_for_pid(1234) == _classid_for_pid(1234)

    def test_unique_for_different_pids(self) -> None:
        assert _classid_for_pid(100) != _classid_for_pid(200)

    def test_major_is_0x0010(self) -> None:
        classid = _classid_for_pid(42)
        assert (classid >> 16) == 0x0010

    def test_minor_is_pid_lower_16_bits(self) -> None:
        assert (_classid_for_pid(42) & 0xFFFF) == 42
        assert (_classid_for_pid(0xABCD) & 0xFFFF) == 0xABCD

    def test_large_pid_wraps_to_16_bits(self) -> None:
        pid = 0x1FFFF
        assert (_classid_for_pid(pid) & 0xFFFF) == (pid & 0xFFFF)


class TestCgroupV2Block:
    """Tests for _cgroup_v2_block with mocked filesystem and subprocess."""

    def test_returns_false_when_cgroup_v2_unavailable(self) -> None:
        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=False
        ):
            assert _cgroup_v2_block(1234) is False

    def test_returns_false_when_net_cls_not_in_controllers(self, tmp_path: Path) -> None:
        controllers_file = tmp_path / "cgroup.controllers"
        controllers_file.write_text("cpu memory io\n")

        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=True
        ), mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path):
            assert _cgroup_v2_block(1234) is False

    def test_success_creates_cgroup_and_iptables_rule(self, tmp_path: Path) -> None:
        controllers_file = tmp_path / "cgroup.controllers"
        controllers_file.write_text("cpu memory net_cls io\n")
        subtree_file = tmp_path / "cgroup.subtree_control"
        subtree_file.write_text("cpu memory\n")

        pid = 5678
        expected_classid = _classid_for_pid(pid)

        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=True
        ), mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0, stderr="")
            result = _cgroup_v2_block(pid)

        assert result is True

        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        assert cgroup_dir.exists()
        assert (cgroup_dir / "cgroup.procs").read_text().strip() == str(pid)
        assert (cgroup_dir / "net_cls.classid").read_text().strip() == str(
            expected_classid
        )

        # net_cls was enabled in subtree_control
        assert "+net_cls" in subtree_file.read_text()

        m_run.assert_called_once()
        call_args = m_run.call_args[0][0]
        assert "iptables" in call_args[0]
        assert str(expected_classid) in call_args

    def test_skips_subtree_enable_when_already_set(self, tmp_path: Path) -> None:
        controllers_file = tmp_path / "cgroup.controllers"
        controllers_file.write_text("net_cls\n")
        subtree_file = tmp_path / "cgroup.subtree_control"
        subtree_file.write_text("net_cls\n")

        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=True
        ), mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0, stderr="")
            assert _cgroup_v2_block(100) is True

        assert subtree_file.read_text().strip() == "net_cls"

    def test_rollback_on_iptables_failure(self, tmp_path: Path) -> None:
        controllers_file = tmp_path / "cgroup.controllers"
        controllers_file.write_text("net_cls\n")

        pid = 9999
        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=True
        ), mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(
                returncode=1, stderr="iptables: No chain/target/match"
            )
            result = _cgroup_v2_block(pid)

        assert result is False
        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        assert not cgroup_dir.exists()

    def test_rollback_on_unexpected_exception(self, tmp_path: Path) -> None:
        controllers_file = tmp_path / "cgroup.controllers"
        controllers_file.write_text("net_cls\n")

        pid = 7777

        with mock.patch(
            "enforcement.network_block._cgroup_v2_available", return_value=True
        ), mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "enforcement.network_block.subprocess.run",
            side_effect=OSError("disk full"),
        ):
            result = _cgroup_v2_block(pid)

        assert result is False


class TestCgroupV2Unblock:
    def test_returns_false_when_no_cgroup_dir(self, tmp_path: Path) -> None:
        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path):
            assert _cgroup_v2_unblock(1234) is False

    def test_removes_iptables_rule_and_cgroup_dir(self, tmp_path: Path) -> None:
        pid = 4321
        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        cgroup_dir.mkdir()
        (cgroup_dir / "cgroup.procs").write_text("")

        root_procs = tmp_path / "cgroup.procs"
        root_procs.write_text("")

        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0)
            result = _cgroup_v2_unblock(pid)

        assert result is True
        assert not cgroup_dir.exists()
        m_run.assert_called_once()
        call_args = m_run.call_args[0][0]
        assert call_args[1] == "-D"

    def test_still_removes_cgroup_on_iptables_error(self, tmp_path: Path) -> None:
        pid = 111
        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        cgroup_dir.mkdir()
        (cgroup_dir / "cgroup.procs").write_text("")
        (tmp_path / "cgroup.procs").write_text("")

        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run", side_effect=FileNotFoundError("no iptables")
        ):
            result = _cgroup_v2_unblock(pid)

        assert result is True
        assert not cgroup_dir.exists()


class TestRemoveCgroup:
    def test_migrates_procs_back_to_root(self, tmp_path: Path) -> None:
        pid = 500
        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        cgroup_dir.mkdir()
        (cgroup_dir / "cgroup.procs").write_text("500\n501\n")
        root_procs = tmp_path / "cgroup.procs"
        root_procs.write_text("")

        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path):
            _remove_cgroup(pid)

        assert not cgroup_dir.exists()

    def test_noop_when_dir_missing(self, tmp_path: Path) -> None:
        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path):
            _remove_cgroup(999)


class TestBlockLinuxIntegration:
    """_block_linux should try cgroup first, fall back to UID-owner."""

    def test_uses_cgroup_when_available(self) -> None:
        with mock.patch(
            "enforcement.network_block._cgroup_v2_block", return_value=True
        ) as m_cgroup:
            result = _block_linux({1000})

        assert result is True
        m_cgroup.assert_called_once_with(1000)

    def test_falls_back_to_uid_when_cgroup_unavailable(self) -> None:
        with mock.patch(
            "enforcement.network_block._cgroup_v2_block", return_value=False
        ), mock.patch(
            "enforcement.network_block._get_uid_linux", return_value=1001
        ), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0, stderr="")
            result = _block_linux({2000})

        assert result is True
        m_run.assert_called_once()
        call_args = m_run.call_args[0][0]
        assert "--uid-owner" in call_args

    def test_multiple_pids_mixed(self) -> None:
        call_count = {"n": 0}

        def cgroup_side_effect(pid: int) -> bool:
            call_count["n"] += 1
            return pid == 100

        with mock.patch(
            "enforcement.network_block._cgroup_v2_block",
            side_effect=cgroup_side_effect,
        ), mock.patch(
            "enforcement.network_block._get_uid_linux", return_value=1001
        ), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0, stderr="")
            result = _block_linux({100, 200})

        assert result is True
        assert call_count["n"] == 2


class TestUnblockLinuxIntegration:
    def test_uses_cgroup_unblock_when_dir_exists(self, tmp_path: Path) -> None:
        pid = 300
        cgroup_dir = tmp_path / f"{CGROUP_DIR_PREFIX}-{pid}"
        cgroup_dir.mkdir()
        (cgroup_dir / "cgroup.procs").write_text("")
        (tmp_path / "cgroup.procs").write_text("")

        with mock.patch("enforcement.network_block.CGROUP_BASE", tmp_path), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0)
            result = _unblock_linux({pid})

        assert result is True

    def test_falls_back_to_uid_unblock(self) -> None:
        with mock.patch(
            "enforcement.network_block._cgroup_v2_unblock", return_value=False
        ), mock.patch(
            "enforcement.network_block._get_uid_linux", return_value=1001
        ), mock.patch(
            "subprocess.run"
        ) as m_run:
            m_run.return_value = mock.Mock(returncode=0)
            result = _unblock_linux({400})

        assert result is True


class TestCleanupLinuxCgroups:
    def _make_fake_proc_exist(self, pid: int, alive: bool) -> mock._patch:
        """Return a context-manager patch that controls /proc/{pid} existence."""
        target = f"/proc/{pid}"
        original_exists = Path.exists

        def patched_exists(self_path: Path) -> bool:
            if str(self_path) == target:
                return alive
            return original_exists(self_path)

        return mock.patch.object(Path, "exists", patched_exists)

    def test_removes_stale_cgroup_dirs(self, tmp_path: Path) -> None:
        stale_pid = 99999
        stale_dir = tmp_path / f"detec-block-{stale_pid}"
        stale_dir.mkdir()
        (stale_dir / "cgroup.procs").write_text(f"{stale_pid}\n")
        (tmp_path / "cgroup.procs").write_text("")

        with mock.patch("enforcement.cleanup.CGROUP_BASE", tmp_path), \
             self._make_fake_proc_exist(stale_pid, alive=False):
            cleaned = _cleanup_linux_cgroups()

        assert cleaned == 1
        assert not stale_dir.exists()

    def test_skips_dir_with_live_pid(self, tmp_path: Path) -> None:
        live_pid = 77777
        live_dir = tmp_path / f"detec-block-{live_pid}"
        live_dir.mkdir()
        (live_dir / "cgroup.procs").write_text(f"{live_pid}\n")

        with mock.patch("enforcement.cleanup.CGROUP_BASE", tmp_path), \
             self._make_fake_proc_exist(live_pid, alive=True):
            cleaned = _cleanup_linux_cgroups()

        assert cleaned == 0
        assert live_dir.exists()

    def test_no_cgroup_dirs_returns_zero(self, tmp_path: Path) -> None:
        with mock.patch("enforcement.cleanup.CGROUP_BASE", tmp_path):
            assert _cleanup_linux_cgroups() == 0

    def test_ignores_non_numeric_suffix(self, tmp_path: Path) -> None:
        bad_dir = tmp_path / "detec-block-notanumber"
        bad_dir.mkdir()

        with mock.patch("enforcement.cleanup.CGROUP_BASE", tmp_path):
            assert _cleanup_linux_cgroups() == 0
        assert bad_dir.exists()

    def test_handles_non_directory_entries(self, tmp_path: Path) -> None:
        (tmp_path / "detec-block-12345").write_text("not a dir")

        with mock.patch("enforcement.cleanup.CGROUP_BASE", tmp_path):
            assert _cleanup_linux_cgroups() == 0
