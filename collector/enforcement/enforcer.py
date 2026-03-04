"""Enforcement dispatcher — routes policy decisions to concrete tactics.

The enforcement ladder:

| Tactic           | Decision   | Module          |
|------------------|------------|-----------------|
| Log & Alert      | detect/warn| (default — emit event only) |
| Process Kill     | block      | process_kill.py |
| Network Block    | block+NET  | network_block.py|
| Environment Proxy| any        | proxy_inject.py |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.policy import PolicyDecision

logger = logging.getLogger(__name__)


@dataclass
class EnforcementResult:
    tactic: str
    success: bool
    detail: str = ""
    tool_name: str = ""
    pid: int | None = None


class Enforcer:
    """Dispatch enforcement actions based on policy decisions."""

    def __init__(self, dry_run: bool = False) -> None:
        self._dry_run = dry_run
        self._results: list[EnforcementResult] = []

    def enforce(
        self,
        decision: PolicyDecision,
        tool_name: str,
        tool_class: str,
        pids: set[int] | None = None,
        network_elevated: bool = False,
    ) -> EnforcementResult:
        """Select and execute the appropriate enforcement tactic."""

        if decision.decision_state in ("detect", "warn"):
            result = EnforcementResult(
                tactic="log_and_alert",
                success=True,
                detail=f"Logged {decision.decision_state} for {tool_name}",
                tool_name=tool_name,
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

    def _process_kill(self, tool_name: str, pids: set[int]) -> EnforcementResult:
        from enforcement.process_kill import kill_processes
        if self._dry_run:
            result = EnforcementResult(
                tactic="process_kill",
                success=True,
                detail=f"[DRY RUN] Would kill PIDs {pids} for {tool_name}",
                tool_name=tool_name,
            )
        else:
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
        if self._dry_run:
            result = EnforcementResult(
                tactic="network_null_route",
                success=True,
                detail=f"[DRY RUN] Would block network for {tool_name} PIDs {pids}",
                tool_name=tool_name,
            )
        else:
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
