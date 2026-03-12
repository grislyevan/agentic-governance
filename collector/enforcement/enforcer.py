"""Enforcement dispatcher -- routes policy decisions to concrete tactics.

The enforcement ladder:

| Tactic           | Decision   | Module          |
|------------------|------------|-----------------|
| Log & Alert      | detect/warn| (default -- emit event only) |
| Process Kill     | block      | process_kill.py |
| Network Block    | block+NET  | network_block.py|
| Environment Proxy| any        | proxy_inject.py |

Posture controls whether tactics actually execute:

| Posture  | Behavior                                      |
|----------|-----------------------------------------------|
| passive  | Log only, never call OS-level enforcement     |
| audit    | Dry-run: compute what would happen, emit event|
| active   | Execute enforcement when confidence >= threshold|
"""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.policy import PolicyDecision

if TYPE_CHECKING:
    from enforcement.posture import PostureManager

logger = logging.getLogger(__name__)

_RESURRECTION_WINDOW = 300.0
_RESURRECTION_THRESHOLD = 3


@dataclass
class EnforcementResult:
    tactic: str
    success: bool
    detail: str = ""
    tool_name: str = ""
    pid: int | None = None
    simulated: bool = False
    allow_listed: bool = False
    escalated: bool = False
    rate_limited: bool = False
    escalation_details: list[str] = field(default_factory=list)


class Enforcer:
    """Dispatch enforcement actions based on policy decisions and posture."""

    def __init__(
        self,
        posture_manager: PostureManager | None = None,
        dry_run: bool = False,
        max_enforcements_per_minute: int = 5,
    ) -> None:
        self._posture_mgr = posture_manager
        self._dry_run = dry_run
        self._results: list[EnforcementResult] = []
        from enforcement.rate_limiter import EnforcementRateLimiter
        self._rate_limiter = EnforcementRateLimiter(max_per_minute=max_enforcements_per_minute)
        self._kill_history: dict[str, deque[float]] = {}
        self._kill_history_lock = threading.Lock()

    @property
    def posture(self) -> str:
        if self._posture_mgr:
            return self._posture_mgr.posture
        return "passive" if not self._dry_run else "audit"

    def enforce(
        self,
        decision: PolicyDecision,
        tool_name: str,
        tool_class: str,
        pids: set[int] | None = None,
        network_elevated: bool = False,
        process_patterns: list[str] | None = None,
    ) -> EnforcementResult:
        """Select and execute the appropriate enforcement tactic.

        Respects the current posture:
        - passive: always returns log_and_alert
        - audit: computes the tactic but does not execute (simulated=True)
        - active: executes if confidence >= threshold
        """
        posture = self.posture

        if decision.decision_state in ("detect", "warn"):
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Logged {decision.decision_state} for {tool_name}",
                tool_name=tool_name,
            )
            self._results.append(result)
            return result

        if posture == "passive":
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Posture is passive; logged {decision.decision_state} for {tool_name}",
                tool_name=tool_name,
            )
            self._results.append(result)
            return result

        if self._posture_mgr and self._posture_mgr.is_allow_listed(tool_name):
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Allow-listed: {tool_name}",
                tool_name=tool_name,
                allow_listed=True,
            )
            self._results.append(result)
            return result

        if posture == "audit" or self._dry_run:
            return self._simulate(decision, tool_name, tool_class, pids, network_elevated)

        # Staleness gate (Task 11a): if the allow-list hasn't been synced
        # recently, downgrade to audit to avoid killing a tool that was
        # exempted on the server but hasn't reached this agent yet.
        if self._posture_mgr and not self._posture_mgr.is_allow_list_fresh():
            age = self._posture_mgr.allow_list_age_seconds
            logger.warning(
                "Allow-list data is %.0fs old; downgrading to audit for %s",
                age, tool_name,
            )
            result = self._simulate(decision, tool_name, tool_class, pids, network_elevated)
            result.detail = (
                f"[STALE ALLOW-LIST] {result.detail} "
                f"(allow-list age: {age:.0f}s, enforcement deferred to audit)"
            )
            return result

        # posture == "active": check confidence threshold
        if self._posture_mgr:
            threshold = self._posture_mgr.auto_enforce_threshold
            if decision.decision_confidence < threshold:
                result = EnforcementResult(
                    tactic="log_and_alert",
                    success=True,
                    detail=(
                        f"Confidence {decision.decision_confidence:.2f} below "
                        f"threshold {threshold:.2f} for {tool_name}"
                    ),
                    tool_name=tool_name,
                    simulated=True,
                )
                self._results.append(result)
                return result

        if not self._rate_limiter.allow():
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Rate limited: {self._rate_limiter.recent_count} enforcements in window for {tool_name}",
                tool_name=tool_name,
                simulated=True,
                rate_limited=True,
            )
            self._results.append(result)
            logger.warning("Enforcement rate limited for %s", tool_name)
            return result

        if decision.decision_state == "block":
            if network_elevated:
                return self._network_block(tool_name, pids or set())
            if pids:
                expected_pattern = (process_patterns or [None])[0] if process_patterns else None
                return self._process_kill(tool_name, pids, expected_pattern=expected_pattern)
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Block decision for {tool_name} but no PIDs available for enforcement",
                tool_name=tool_name,
            )
            self._results.append(result)
            return result

        if decision.decision_state == "approval_required":
            result = EnforcementResult(
                tactic="hold_pending_approval",
                success=True,
                detail=f"Holding {tool_name} pending approval",
                tool_name=tool_name,
            )
            self._results.append(result)
            return result

        result = EnforcementResult(
            tactic="log_and_alert",
            success=True,
            detail=f"Unrecognized decision state: {decision.decision_state}",
            tool_name=tool_name,
        )
        self._results.append(result)
        return result

    def _simulate(
        self,
        decision: PolicyDecision,
        tool_name: str,
        tool_class: str,
        pids: set[int] | None,
        network_elevated: bool,
    ) -> EnforcementResult:
        """Compute what enforcement would do without executing it."""
        if decision.decision_state == "block":
            if network_elevated:
                tactic = "network_null_route"
                detail = f"[AUDIT] Would block network for {tool_name} PIDs {pids or set()}"
            elif pids:
                tactic = "process_kill"
                detail = f"[AUDIT] Would kill PIDs {pids} for {tool_name}"
            else:
                tactic = "log_and_alert"
                detail = f"[AUDIT] Block for {tool_name} but no PIDs available"
        elif decision.decision_state == "approval_required":
            tactic = "hold_pending_approval"
            detail = f"[AUDIT] Would hold {tool_name} pending approval"
        else:
            tactic = "log_and_alert"
            detail = f"[AUDIT] {decision.decision_state} for {tool_name}"

        result = EnforcementResult(
            tactic=tactic,
            success=True,
            detail=detail,
            tool_name=tool_name,
            simulated=True,
        )
        self._results.append(result)
        return result

    def _process_kill(
        self,
        tool_name: str,
        pids: set[int],
        expected_pattern: str | None = None,
    ) -> EnforcementResult:
        from enforcement.process_kill import kill_process_tree

        target_pid = next((p for p in pids if p > 1), None)
        parent_ppid: int | None = None
        target_exe: str | None = None
        if target_pid:
            try:
                import psutil
                proc = psutil.Process(target_pid)
                parent_ppid = proc.ppid()
                target_exe = proc.exe()
            except Exception:
                pass

        all_killed: list[int] = []
        for pid in pids:
            if pid <= 1:
                continue
            kr = kill_process_tree(pid, expected_pattern=expected_pattern)
            if kr.success and kr.killed_pids:
                all_killed.extend(kr.killed_pids)

        self._rate_limiter.record()

        escalated = self._check_resurrection(tool_name)
        escalation_details: list[str] = []

        if escalated:
            if parent_ppid and parent_ppid > 1:
                try:
                    kr = kill_process_tree(parent_ppid, grace_period=5.0)
                    if kr.success:
                        escalation_details.append(f"killed parent {parent_ppid}")
                        logger.info("Escalation: killed parent PID %d for %s", parent_ppid, tool_name)
                    else:
                        escalation_details.append(f"parent kill failed: {kr.detail}")
                        logger.warning("Escalation: failed to kill parent %d: %s", parent_ppid, kr.detail)
                except Exception as exc:
                    escalation_details.append(f"parent kill error: {exc}")
                    logger.warning("Escalation: error killing parent %d: %s", parent_ppid, exc)

            if platform.system() == "Linux" and target_pid:
                try:
                    with open(f"/proc/{target_pid}/cgroup") as f:
                        for line in f:
                            if "::" in line and (".service" in line or ".slice" in line):
                                path = line.strip().split("::", 1)[-1].strip()
                                for part in path.split("/"):
                                    if part.endswith(".service"):
                                        disable = subprocess.run(
                                            ["systemctl", "disable", "--now", part],
                                            capture_output=True, text=True, timeout=10,
                                        )
                                        if disable.returncode == 0:
                                            escalation_details.append(f"disabled unit {part}")
                                            logger.info("Escalation: disabled systemd unit %s", part)
                                        break
                                break
                except Exception as exc:
                    logger.debug("Escalation: systemd unit check failed: %s", exc)

            if platform.system() == "Darwin" and target_exe:
                try:
                        for plist_dir in [
                            "/Library/LaunchDaemons",
                            "/Library/LaunchAgents",
                            "/Users/*/Library/LaunchAgents",
                        ]:
                            try:
                                from pathlib import Path
                                import glob
                                for path in glob.glob(plist_dir + "/*.plist"):
                                    try:
                                        with open(path) as f:
                                            if target_exe in f.read():
                                                escalation_details.append(f"found plist {path}")
                                                logger.info("Escalation: found launchd plist %s for %s", path, target_exe)
                                                break
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception as exc:
                    logger.debug("Escalation: launchd check failed: %s", exc)

        detail = f"Killed PIDs {all_killed} for {tool_name}"
        if escalated:
            detail = f"Escalated: {detail} (killed 3+ times in 5 min)"

        result = EnforcementResult(
            tactic="process_kill",
            success=len(all_killed) > 0,
            detail=detail,
            tool_name=tool_name,
            escalated=escalated,
            escalation_details=escalation_details,
        )
        self._results.append(result)
        return result

    def _check_resurrection(self, tool_name: str) -> bool:
        """Track kill history; return True if tool was killed 3+ times in 5 min."""
        now = time.monotonic()
        with self._kill_history_lock:
            if tool_name not in self._kill_history:
                self._kill_history[tool_name] = deque()
            hist = self._kill_history[tool_name]
            cutoff = now - _RESURRECTION_WINDOW
            while hist and hist[0] < cutoff:
                hist.popleft()
            hist.append(now)
            return len(hist) >= _RESURRECTION_THRESHOLD

    def _network_block(self, tool_name: str, pids: set[int]) -> EnforcementResult:
        from enforcement.network_block import block_outbound
        blocked = block_outbound(pids)
        result = EnforcementResult(
            tactic="network_null_route",
            success=blocked,
            detail=f"Network block {'applied' if blocked else 'failed'} for {tool_name}",
            tool_name=tool_name,
        )
        self._results.append(result)
        return result

    @property
    def results(self) -> list[EnforcementResult]:
        return list(self._results)
