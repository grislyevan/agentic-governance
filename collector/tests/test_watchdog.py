"""Tests for collector/watchdog.py.

Uses unittest.mock.patch to stub out subprocess.run so no real system
calls are made.  All tests run cross-platform (including macOS/Linux CI).
"""

from __future__ import annotations

import subprocess
import types
import unittest
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """Build a fake CompletedProcess for use in mock side-effects."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# is_agent_running
# ---------------------------------------------------------------------------

class TestIsAgentRunning(unittest.TestCase):

    def test_is_agent_running_true(self) -> None:
        """tasklist returns output containing detec-agent.exe → True."""
        mock_result = _make_completed(stdout='"detec-agent.exe","1234","Console","1","12,345 K"\r\n')
        with patch("watchdog.subprocess.run", return_value=mock_result) as mock_run:
            from watchdog import is_agent_running
            result = is_agent_running()

        self.assertTrue(result)
        mock_run.assert_called_once()

    def test_is_agent_running_false(self) -> None:
        """tasklist returns empty output (no matching process) → False."""
        mock_result = _make_completed(stdout="INFO: No tasks are running which match the specified criteria.\r\n")
        with patch("watchdog.subprocess.run", return_value=mock_result):
            from watchdog import is_agent_running
            result = is_agent_running()

        self.assertFalse(result)

    def test_is_agent_running_exception_returns_false(self) -> None:
        """If subprocess.run raises an exception, returns False without crashing."""
        with patch("watchdog.subprocess.run", side_effect=OSError("no such file")):
            from watchdog import is_agent_running
            result = is_agent_running()

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# is_task_registered
# ---------------------------------------------------------------------------

class TestIsTaskRegistered(unittest.TestCase):

    def test_is_task_registered_true(self) -> None:
        """schtasks /query exits 0 → task exists → True."""
        mock_result = _make_completed(returncode=0, stdout="TaskName: DetecAgent\r\n")
        with patch("watchdog.subprocess.run", return_value=mock_result):
            from watchdog import is_task_registered
            result = is_task_registered("DetecAgent")

        self.assertTrue(result)

    def test_is_task_registered_false(self) -> None:
        """schtasks /query exits non-zero → task missing → False."""
        mock_result = _make_completed(returncode=1, stderr="ERROR: The system cannot find the file specified.\r\n")
        with patch("watchdog.subprocess.run", return_value=mock_result):
            from watchdog import is_task_registered
            result = is_task_registered("DetecAgent")

        self.assertFalse(result)

    def test_is_task_registered_exception_returns_false(self) -> None:
        """If subprocess.run raises, returns False without crashing."""
        with patch("watchdog.subprocess.run", side_effect=OSError("not found")):
            from watchdog import is_task_registered
            result = is_task_registered("DetecAgent")

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# restart_agent
# ---------------------------------------------------------------------------

class TestRestartAgent(unittest.TestCase):

    def test_restart_agent_creates_task_if_missing(self) -> None:
        """When task is not registered, schtasks /create should be called."""
        # is_task_registered uses schtasks /query (returncode=1 → missing)
        # then restart_agent calls schtasks /create (returncode=0)
        # then restart_agent calls schtasks /run (returncode=0)
        side_effects = [
            _make_completed(returncode=1),   # is_task_registered → False
            _make_completed(returncode=0),   # schtasks /create
            _make_completed(returncode=0),   # schtasks /run
        ]
        with patch("watchdog.subprocess.run", side_effect=side_effects) as mock_run:
            from watchdog import restart_agent
            restart_agent()

        calls = mock_run.call_args_list
        self.assertEqual(len(calls), 3)
        # Second call should be schtasks /create
        create_cmd = calls[1][0][0]
        self.assertIn("/create", create_cmd)
        self.assertIn("DetecAgent", create_cmd)

    def test_restart_agent_runs_task(self) -> None:
        """schtasks /run should always be called when task is already registered."""
        side_effects = [
            _make_completed(returncode=0),   # is_task_registered → True
            _make_completed(returncode=0),   # schtasks /run
        ]
        with patch("watchdog.subprocess.run", side_effect=side_effects) as mock_run:
            from watchdog import restart_agent
            restart_agent()

        calls = mock_run.call_args_list
        self.assertEqual(len(calls), 2)
        # Second call should be schtasks /run
        run_cmd = calls[1][0][0]
        self.assertIn("/run", run_cmd)
        self.assertIn("DetecAgent", run_cmd)

    def test_restart_agent_aborts_if_create_fails(self) -> None:
        """If schtasks /create fails, schtasks /run should NOT be called."""
        side_effects = [
            _make_completed(returncode=1),   # is_task_registered → False
            _make_completed(returncode=1, stderr="Access denied"),  # /create fails
        ]
        with patch("watchdog.subprocess.run", side_effect=side_effects) as mock_run:
            from watchdog import restart_agent
            restart_agent()

        # Only 2 calls: query + create.  /run should NOT have been called.
        self.assertEqual(mock_run.call_count, 2)


# ---------------------------------------------------------------------------
# run_watchdog (smoke test — does not let the loop run indefinitely)
# ---------------------------------------------------------------------------

class TestRunWatchdog(unittest.TestCase):

    def test_run_watchdog_calls_restart_when_agent_missing(self) -> None:
        """run_watchdog should call restart_agent once when agent is not running,
        then stop after the first iteration via a patched time.sleep that raises
        StopIteration to break the infinite loop."""

        call_count = {"n": 0}

        def fake_sleep(_seconds: float) -> None:
            call_count["n"] += 1
            if call_count["n"] >= 1:
                raise StopIteration("test sentinel")

        with (
            patch("watchdog.is_agent_running", return_value=False),
            patch("watchdog.restart_agent") as mock_restart,
            patch("watchdog.time.sleep", side_effect=fake_sleep),
        ):
            from watchdog import run_watchdog
            with self.assertRaises(StopIteration):
                run_watchdog()

        mock_restart.assert_called_once()

    def test_run_watchdog_does_not_call_restart_when_agent_running(self) -> None:
        """run_watchdog should NOT call restart_agent when agent is alive."""

        call_count = {"n": 0}

        def fake_sleep(_seconds: float) -> None:
            call_count["n"] += 1
            if call_count["n"] >= 1:
                raise StopIteration("test sentinel")

        with (
            patch("watchdog.is_agent_running", return_value=True),
            patch("watchdog.restart_agent") as mock_restart,
            patch("watchdog.time.sleep", side_effect=fake_sleep),
        ):
            from watchdog import run_watchdog
            with self.assertRaises(StopIteration):
                run_watchdog()

        mock_restart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
