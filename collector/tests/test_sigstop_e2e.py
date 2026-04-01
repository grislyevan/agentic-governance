"""Real end-to-end smoke tests for SIGSTOP-based approval hold.

Unlike the unit tests in test_process_suspend.py which mock os.kill, these
tests spawn real subprocesses, actually SIGSTOP them, and verify that
process suspension works at the OS level.

Requirements:
  - Unix (macOS or Linux) -- tests are skipped on Windows.
  - psutil must be installed.

Run separately:
  python -m pytest collector/tests/test_sigstop_e2e.py -v -m e2e
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from enforcement.process_suspend import resume_processes, suspend_processes

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

_SKIP_WINDOWS = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="SIGSTOP not available on Windows",
)

e2e = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def child_sleeper():
    """Spawn a long-running subprocess that sleeps in a loop.

    Yields the Popen object. Always terminates + reaps the child in cleanup,
    even if the child is currently stopped (SIGCONT first, then kill).
    """
    proc = subprocess.Popen(
        ["python3", "-c", "import time\nwhile True:\n time.sleep(0.05)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield proc

    # Cleanup: resume if stopped, then terminate
    try:
        os.kill(proc.pid, signal.SIGCONT)
    except OSError:
        pass
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


@pytest.fixture()
def child_writer(tmp_path):
    """Spawn a subprocess that writes a counter to a temp file every ~50ms.

    Yields (proc, path_to_file). Cleanup is identical to child_sleeper.
    """
    outfile = tmp_path / "counter.txt"
    # The script writes an incrementing integer on each line, flushing each time.
    script = (
        "import time, sys\n"
        f"f = open({str(outfile)!r}, 'w')\n"
        "i = 0\n"
        "while True:\n"
        "    f.write(str(i) + '\\n')\n"
        "    f.flush()\n"
        "    i += 1\n"
        "    time.sleep(0.05)\n"
    )
    proc = subprocess.Popen(
        ["python3", "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield proc, outfile

    try:
        os.kill(proc.pid, signal.SIGCONT)
    except OSError:
        pass
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


def _line_count(path: Path) -> int:
    """Return the number of lines in a file, 0 if it does not exist yet."""
    try:
        return len(path.read_text().splitlines())
    except FileNotFoundError:
        return 0


def _wait_for_status(pid: int, target_status: str, timeout: float = 3.0) -> bool:
    """Poll psutil until the process reaches *target_status* or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            st = psutil.Process(pid).status()
            if st == target_status:
                return True
        except psutil.NoSuchProcess:
            return False
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------------------
# Test 1: real SIGSTOP freezes a subprocess
# ---------------------------------------------------------------------------


@_SKIP_WINDOWS
@e2e
class TestRealSigstopFreezesSubprocess:

    def test_real_sigstop_freezes_subprocess(self, child_sleeper) -> None:
        proc = child_sleeper

        # Ensure subprocess is alive and running
        assert proc.poll() is None
        assert _wait_for_status(proc.pid, psutil.STATUS_RUNNING) or \
               _wait_for_status(proc.pid, psutil.STATUS_SLEEPING), \
            f"Child not running; status={psutil.Process(proc.pid).status()}"

        # Suspend via the production function
        result = suspend_processes({proc.pid})
        assert result[proc.pid] is True

        # Verify the process is actually stopped
        assert _wait_for_status(proc.pid, psutil.STATUS_STOPPED, timeout=2.0), \
            f"Expected STOPPED, got {psutil.Process(proc.pid).status()}"

        # Resume via the production function
        result = resume_processes({proc.pid})
        assert result[proc.pid] is True

        # Verify the process is running again (running or sleeping)
        time.sleep(0.1)
        status = psutil.Process(proc.pid).status()
        assert status != psutil.STATUS_STOPPED, \
            f"Process should not be stopped after SIGCONT, got {status}"


# ---------------------------------------------------------------------------
# Test 2: SIGSTOP blocks output
# ---------------------------------------------------------------------------


@_SKIP_WINDOWS
@e2e
class TestRealSigstopBlocksOutput:

    def test_real_sigstop_blocks_output(self, child_writer) -> None:
        proc, outfile = child_writer

        # Wait for the subprocess to start writing
        deadline = time.monotonic() + 3.0
        while _line_count(outfile) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _line_count(outfile) >= 2, "Child never started writing"

        # Verify file is growing
        count_before_stop = _line_count(outfile)
        time.sleep(0.3)
        count_after_wait = _line_count(outfile)
        assert count_after_wait > count_before_stop, \
            "File should be growing before SIGSTOP"

        # SIGSTOP the process
        suspend_processes({proc.pid})
        assert _wait_for_status(proc.pid, psutil.STATUS_STOPPED, timeout=2.0)

        # Wait and verify file did NOT grow (process is frozen)
        count_at_stop = _line_count(outfile)
        time.sleep(0.5)
        count_after_stop_wait = _line_count(outfile)
        assert count_after_stop_wait == count_at_stop, \
            f"File grew while stopped: {count_at_stop} -> {count_after_stop_wait}"

        # SIGCONT the process
        resume_processes({proc.pid})
        time.sleep(0.5)

        # Verify file is growing again
        count_after_resume = _line_count(outfile)
        assert count_after_resume > count_at_stop, \
            f"File should grow after resume: stuck at {count_at_stop}"


# ---------------------------------------------------------------------------
# Test 3: ApprovalHoldManager with real suspension
# ---------------------------------------------------------------------------


@_SKIP_WINDOWS
@e2e
class TestApprovalHoldWithRealSuspension:

    def test_approval_hold_with_real_suspension(self, child_writer) -> None:
        from enforcement.approval_hold import ApprovalHoldManager, HoldConfig

        proc, outfile = child_writer

        # Wait for child to start writing
        deadline = time.monotonic() + 3.0
        while _line_count(outfile) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _line_count(outfile) >= 2, "Child never started writing"

        # Build a manager with fast polling
        config = HoldConfig(
            poll_interval_seconds=0,
            timeout_seconds=10,
        )
        manager = ApprovalHoldManager(
            api_url="http://localhost:9999/api",
            api_key="test-key",
            config=config,
        )

        # Mock _create_approval_request to return a fake ID
        # Mock _poll_decision to return "approved" after ~0.8 seconds
        poll_start_time = [None]

        def _fake_poll(approval_id):
            if poll_start_time[0] is None:
                poll_start_time[0] = time.monotonic()
            elapsed = time.monotonic() - poll_start_time[0]
            if elapsed < 0.8:
                return "pending"
            return "approved"

        with patch.object(manager, "_create_approval_request", return_value="ar-e2e"), \
             patch.object(manager, "_poll_decision", side_effect=_fake_poll):

            # Record line count just before the hold
            count_before_hold = _line_count(outfile)

            result = manager.wait_for_decision(
                event_id="evt-e2e",
                tool_name="test-agent",
                tool_class="C",
                confidence_band="high",
                confidence_score=0.9,
                policy_rule_id="RULE-E2E",
                pids={proc.pid},
                suspend_on_hold=True,
                max_suspend_seconds=10,
            )

        assert result.decision == "approved"
        assert result.hold_effective is True

        # After approval, the process should be resumed and writing again
        time.sleep(0.5)
        count_after_resume = _line_count(outfile)
        assert count_after_resume > count_before_hold, \
            f"File should grow after approval resume: {count_before_hold} -> {count_after_resume}"


# ---------------------------------------------------------------------------
# Test 4: Denial leaves process frozen
# ---------------------------------------------------------------------------


@_SKIP_WINDOWS
@e2e
class TestApprovalDenyLeavesProcessFrozen:

    def test_approval_deny_leaves_process_frozen(self, child_writer) -> None:
        from enforcement.approval_hold import ApprovalHoldManager, HoldConfig

        proc, outfile = child_writer

        # Wait for child to start writing
        deadline = time.monotonic() + 3.0
        while _line_count(outfile) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _line_count(outfile) >= 2

        config = HoldConfig(
            poll_interval_seconds=0,
            timeout_seconds=10,
        )
        manager = ApprovalHoldManager(
            api_url="http://localhost:9999/api",
            api_key="test-key",
            config=config,
        )

        poll_start_time = [None]

        def _fake_poll(approval_id):
            if poll_start_time[0] is None:
                poll_start_time[0] = time.monotonic()
            elapsed = time.monotonic() - poll_start_time[0]
            if elapsed < 0.8:
                return "pending"
            return "denied"

        with patch.object(manager, "_create_approval_request", return_value="ar-deny"), \
             patch.object(manager, "_poll_decision", side_effect=_fake_poll):

            result = manager.wait_for_decision(
                event_id="evt-deny",
                tool_name="test-agent",
                tool_class="C",
                confidence_band="high",
                confidence_score=0.9,
                policy_rule_id="RULE-DENY",
                pids={proc.pid},
                suspend_on_hold=True,
                max_suspend_seconds=10,
            )

        assert result.decision == "denied"
        assert result.hold_effective is True

        # After denial the process should still be stopped (NOT resumed).
        # The enforcer is expected to kill it instead.
        time.sleep(0.2)
        status = psutil.Process(proc.pid).status()
        assert status == psutil.STATUS_STOPPED, \
            f"Process should remain STOPPED after denial, got {status}"

        # File should NOT have grown since the denial
        count_at_deny = _line_count(outfile)
        time.sleep(0.5)
        count_after = _line_count(outfile)
        assert count_after == count_at_deny, \
            f"File grew after denial: {count_at_deny} -> {count_after}"

        # Cleanup: SIGKILL since it won't resume on its own
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test 5: Safety valve resumes after max_suspend_seconds
# ---------------------------------------------------------------------------


@_SKIP_WINDOWS
@e2e
class TestSafetyValveResumesAfterMaxSeconds:

    def test_safety_valve_resumes_after_max_seconds(self, child_writer) -> None:
        from enforcement.approval_hold import ApprovalHoldManager, HoldConfig

        proc, outfile = child_writer

        # Wait for child to start writing
        deadline = time.monotonic() + 3.0
        while _line_count(outfile) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _line_count(outfile) >= 2

        # Use a very short max_suspend_seconds so safety valve fires fast.
        # timeout_seconds is longer so the poll loop keeps running after resume.
        config = HoldConfig(
            poll_interval_seconds=0,
            timeout_seconds=5,
            timeout_behavior="deny",
        )
        manager = ApprovalHoldManager(
            api_url="http://localhost:9999/api",
            api_key="test-key",
            config=config,
        )

        # _poll_decision always returns "pending" -- never resolves.
        def _forever_pending(approval_id):
            return "pending"

        # We need to control time precisely: the safety valve checks
        # time.monotonic() against the suspend_deadline. We use a fake
        # monotonic that jumps past max_suspend_seconds after a few polls,
        # then past timeout_seconds.

        real_monotonic = time.monotonic
        base = real_monotonic()
        call_count = [0]

        def _fake_monotonic():
            call_count[0] += 1
            # First 2 calls: initial deadline calc + suspend_deadline calc
            if call_count[0] <= 2:
                return base
            # Next call: the safety-valve check. Jump past max_suspend_seconds.
            if call_count[0] <= 5:
                return base + 3.0  # past 2s max_suspend
            # After that, push past timeout so we exit
            return base + 6.0  # past 5s timeout

        count_before = _line_count(outfile)

        with patch.object(manager, "_create_approval_request", return_value="ar-sv"), \
             patch.object(manager, "_poll_decision", side_effect=_forever_pending), \
             patch("enforcement.approval_hold.time.monotonic", side_effect=_fake_monotonic), \
             patch("enforcement.approval_hold.time.sleep"):

            result = manager.wait_for_decision(
                event_id="evt-sv",
                tool_name="test-agent",
                tool_class="C",
                confidence_band="high",
                confidence_score=0.9,
                policy_rule_id="RULE-SV",
                pids={proc.pid},
                suspend_on_hold=True,
                max_suspend_seconds=2,
            )

        assert result.timed_out is True
        assert result.hold_effective is True

        # The safety valve should have resumed the process (via SIGCONT)
        # before the overall timeout expired. Since we mocked time.sleep,
        # the real SIGSTOP/SIGCONT still happened. After the function returns,
        # the process was denied (timeout_behavior=deny), but the safety valve
        # already fired SIGCONT. However, on denial, suspended_pids is cleared
        # so the finally block won't resume again. The process IS actually
        # resumed because _do_resume was called by the safety valve.
        #
        # Verify the process is running (not stopped) after the call.
        time.sleep(0.5)
        status = psutil.Process(proc.pid).status()
        assert status != psutil.STATUS_STOPPED, \
            f"Safety valve should have resumed the process, but status={status}"

        # Verify the file is growing again
        count_after_resume = _line_count(outfile)
        assert count_after_resume > count_before, \
            f"File should grow after safety-valve resume: {count_before} -> {count_after_resume}"
