"""Detec Agent Watchdog.

Standalone module that monitors detec-agent.exe and ensures it keeps running.
The watchdog itself is registered as a Scheduled Task (DetecAgentWatchdog) and
is watched by the main agent — providing mutual monitoring.

Usage (from agent_cli.py subcommand):
    detec-agent watchdog
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

logger = logging.getLogger("detec.watchdog")

_AGENT_EXE = "detec-agent.exe"
_AGENT_TASK_NAME = "DetecAgent"
_WATCHDOG_TASK_NAME = "DetecAgentWatchdog"
_AGENT_EXE_PATH = r"C:\Program Files\Detec\Agent\detec-agent.exe"
_CHECK_INTERVAL = 60  # seconds


def is_agent_running() -> bool:
    """Return True if detec-agent.exe is currently running.

    Uses ``tasklist`` to query the process list; avoids WMI/psutil dependencies
    so the watchdog stays lightweight.
    """
    try:
        result = subprocess.run(
            ["tasklist", "/fi", f"IMAGENAME eq {_AGENT_EXE}", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return _AGENT_EXE.lower() in result.stdout.lower()
    except Exception:
        logger.exception("is_agent_running: tasklist query failed")
        return False


def is_task_registered(task_name: str) -> bool:
    """Return True if the named Scheduled Task exists.

    Uses ``schtasks /query`` which exits 0 when found and non-zero when missing.
    """
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        logger.exception("is_task_registered: schtasks query failed for %s", task_name)
        return False


def restart_agent() -> None:
    """Re-register the DetecAgent Scheduled Task if missing, then start it.

    This is called when the watchdog detects the agent process has died and
    cannot be started simply via /run (because the task itself may be gone).
    """
    logger.warning("Watchdog: agent not running — attempting restart")

    if not is_task_registered(_AGENT_TASK_NAME):
        logger.warning("Watchdog: task '%s' not registered — re-creating it", _AGENT_TASK_NAME)
        create_result = subprocess.run(
            [
                "schtasks", "/create",
                "/tn", _AGENT_TASK_NAME,
                "/tr", f"'{_AGENT_EXE_PATH}' run",
                "/sc", "onstart",
                "/ru", "SYSTEM",
                "/rl", "HIGHEST",
                "/f",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if create_result.returncode != 0:
            logger.error(
                "Watchdog: failed to re-create task '%s': %s",
                _AGENT_TASK_NAME,
                create_result.stderr.strip(),
            )
            return

    run_result = subprocess.run(
        ["schtasks", "/run", "/tn", _AGENT_TASK_NAME],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if run_result.returncode == 0:
        logger.warning("Watchdog: task '%s' started successfully", _AGENT_TASK_NAME)
    else:
        logger.error(
            "Watchdog: failed to start task '%s': %s",
            _AGENT_TASK_NAME,
            run_result.stderr.strip(),
        )


def run_watchdog() -> None:
    """Main watchdog loop.

    Checks every ``_CHECK_INTERVAL`` seconds whether detec-agent.exe is running.
    If not, calls ``restart_agent()``.  Exceptions inside the loop are caught and
    logged so the watchdog itself never crashes.
    """
    logger.warning("Watchdog loop starting (check interval: %ds)", _CHECK_INTERVAL)

    while True:
        try:
            if not is_agent_running():
                logger.warning("Watchdog: detec-agent.exe is NOT running")
                restart_agent()
            else:
                logger.debug("Watchdog: detec-agent.exe is running")
        except Exception:
            logger.exception("Watchdog: unexpected error in check loop — continuing")

        time.sleep(_CHECK_INTERVAL)
