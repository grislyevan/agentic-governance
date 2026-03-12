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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.policy import PolicyDecision

if TYPE_CHECKING:
    from enforcement.posture import PostureManager

logger = logging.getLogger(__name__)


@dataclass
class EnforcementResult:
    tactic: str
    success: bool
    detail: str = ""
    tool_name: str = ""
    pid: int | None = None
    simulated: bool = False
    allow_listed: bool = False


class Enforcer:
    """Dispatch enforcement actions based on policy decisions and posture."""

    def __init__(
        self,
        posture_manager: PostureManager | None = None,
        dry_run: bool = False,
    ) -> None:
        self._posture_mgr = posture_manager
        self._dry_run = dry_run
        self._results: list[EnforcementResult] = []

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

        if decision.decision_state == "block":
            if network_elevated:
                return self._network_block(tool_name, pids or set())
            if pids:
                return self._process_kill(tool_name, pids)
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

    def _process_kill(self, tool_name: str, pids: set[int]) -> EnforcementResult:
        from enforcement.process_kill import kill_processes
        killed = kill_processes(pids)
        result = EnforcementResult(
            tactic="process_kill",
            success=len(killed) > 0,
            detail=f"Killed PIDs {killed} for {tool_name}",
            tool_name=tool_name,
        )
        self._results.append(result)
        return result

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
