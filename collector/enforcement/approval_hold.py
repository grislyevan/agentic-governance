"""Approval hold manager: posts ApprovalRequest to server, polls for decision."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class HoldConfig:
    poll_interval_seconds: int = 10
    max_poll_interval_seconds: int = 60
    timeout_seconds: int = 300
    timeout_behavior: str = "deny"   # "deny" | "approve"
    offline_behavior: str = "deny"   # "deny" | "approve"

    def __post_init__(self) -> None:
        valid = {"deny", "approve", "denied", "approved"}
        if self.timeout_behavior not in valid:
            raise ValueError(
                f"Invalid timeout_behavior: {self.timeout_behavior!r}. Must be one of {valid}"
            )
        if self.offline_behavior not in valid:
            raise ValueError(
                f"Invalid offline_behavior: {self.offline_behavior!r}. Must be one of {valid}"
            )

    @classmethod
    def from_dict(cls, d: dict) -> HoldConfig:
        return cls(
            poll_interval_seconds=int(d.get("poll_interval_seconds", 10)),
            max_poll_interval_seconds=int(d.get("max_poll_interval_seconds", 60)),
            timeout_seconds=int(d.get("timeout_seconds", 300)),
            timeout_behavior=d.get("timeout_behavior", "deny"),
            offline_behavior=d.get("offline_behavior", "deny"),
        )


@dataclass
class HoldResult:
    decision: str           # "approved" | "denied"
    approval_id: str | None
    timed_out: bool = False
    hold_effective: bool = False  # True when at least one PID was successfully SIGSTOP'd


def _normalize_decision(behavior: str) -> str:
    """Map config behavior strings to canonical decision values."""
    if behavior in ("deny", "denied"):
        return "denied"
    elif behavior in ("approve", "approved"):
        return "approved"
    else:
        # Should never happen due to HoldConfig validation, but fail secure
        return "denied"


class ApprovalHoldManager:
    """Blocks local enforcement until a server-side approval decision arrives."""

    def __init__(self, api_url: str, api_key: str, config: HoldConfig | None = None) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self.config = config or HoldConfig()

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Content-Type": "application/json"}

    def _create_approval_request(
        self,
        event_id: str,
        tool_name: str,
        tool_class: str,
        confidence_band: str,
        confidence_score: float,
        policy_rule_id: str,
        endpoint_id: str | None = None,
    ) -> str:
        """POST /approvals. Returns approval_id."""
        payload: dict[str, Any] = {
            "event_id": event_id,
            "tool_name": tool_name,
            "tool_class": tool_class,
            "confidence_band": confidence_band,
            "confidence_score": confidence_score,
            "policy_rule_id": policy_rule_id,
        }
        if endpoint_id:
            payload["endpoint_id"] = endpoint_id
        resp = requests.post(
            f"{self._api_url}/approvals",
            json=payload,
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _poll_decision(self, approval_id: str) -> str | None:
        """GET /approvals/:id. Returns status string, or None to signal fast-fail denial."""
        resp = requests.get(
            f"{self._api_url}/approvals/{approval_id}",
            headers=self._headers(),
            timeout=10,
        )
        if resp.status_code in (401, 403, 404):
            logger.warning(
                "Non-transient HTTP %s from approval endpoint for approval_id=%s; failing fast",
                resp.status_code, approval_id,
            )
            return None
        resp.raise_for_status()
        return resp.json()["status"]

    def wait_for_decision(
        self,
        event_id: str,
        tool_name: str,
        tool_class: str,
        confidence_band: str,
        confidence_score: float,
        policy_rule_id: str,
        endpoint_id: str | None = None,
        pids: set[int] | None = None,
        suspend_on_hold: bool = False,
        max_suspend_seconds: int = 60,
    ) -> HoldResult:
        """Block until an approval decision arrives or timeout expires.

        When *suspend_on_hold* is True and *pids* is non-empty, the target
        processes are SIGSTOP'd before polling begins and SIGCONT'd when a
        decision arrives.  A safety valve resumes processes after
        *max_suspend_seconds* even if no decision has been received.
        """
        from enforcement.process_suspend import resume_processes, suspend_processes

        # --- Suspension bookkeeping ---
        suspended_pids: set[int] = set()
        suspend_deadline: float | None = None
        _hold_effective = False

        def _do_suspend() -> None:
            nonlocal suspended_pids, suspend_deadline, _hold_effective
            if suspend_on_hold and pids:
                results = suspend_processes(pids)
                suspended_pids = {pid for pid, ok in results.items() if ok}
                if suspended_pids:
                    _hold_effective = True
                    suspend_deadline = time.monotonic() + max(0, max_suspend_seconds)
                    logger.info(
                        "Suspended %d/%d PIDs for approval hold (max %ds)",
                        len(suspended_pids), len(pids), max_suspend_seconds,
                    )

        def _do_resume() -> None:
            nonlocal suspended_pids
            if suspended_pids:
                resume_processes(suspended_pids)
                logger.info("Resumed %d suspended PIDs", len(suspended_pids))
                suspended_pids = set()

        try:
            approval_id = self._create_approval_request(
                event_id=event_id,
                tool_name=tool_name,
                tool_class=tool_class,
                confidence_band=confidence_band,
                confidence_score=confidence_score,
                policy_rule_id=policy_rule_id,
                endpoint_id=endpoint_id,
            )
        except Exception:
            logger.warning(
                "Could not create approval request for event %s (offline?); "
                "applying offline_behavior=%s",
                event_id, self.config.offline_behavior,
            )
            return HoldResult(decision=_normalize_decision(self.config.offline_behavior), approval_id=None)

        logger.info(
            "Approval hold started: approval_id=%s event_id=%s tool=%s",
            approval_id, event_id, tool_name,
        )

        # Suspend target processes before entering the polling loop.
        _do_suspend()

        try:
            deadline = time.monotonic() + self.config.timeout_seconds
            attempt = 0
            while True:
                # Safety valve: resume suspended processes if max_suspend_seconds exceeded.
                if suspended_pids and suspend_deadline is not None:
                    if time.monotonic() >= suspend_deadline:
                        logger.warning(
                            "Safety valve: resuming %d PIDs after max_suspend_seconds=%d",
                            len(suspended_pids), max_suspend_seconds,
                        )
                        _do_resume()

                try:
                    status = self._poll_decision(approval_id)
                except requests.exceptions.RequestException:
                    logger.warning("Poll failed for approval %s; retrying with backoff", approval_id)
                else:
                    if status is None:
                        # Non-transient HTTP error — fail fast, resume suspended PIDs
                        _do_resume()
                        return HoldResult(
                            decision="denied",
                            approval_id=approval_id,
                            hold_effective=_hold_effective,
                        )
                    if status == "approved":
                        logger.info("Approval decision: approved for approval_id=%s", approval_id)
                        _do_resume()
                        return HoldResult(
                            decision="approved",
                            approval_id=approval_id,
                            hold_effective=_hold_effective,
                        )
                    if status == "denied":
                        logger.info("Approval decision: denied for approval_id=%s", approval_id)
                        # Do NOT resume on denial — let the enforcer kill them.
                        # Clear suspended_pids so the finally block doesn't resume.
                        suspended_pids = set()
                        return HoldResult(
                            decision="denied",
                            approval_id=approval_id,
                            hold_effective=_hold_effective,
                        )

                if time.monotonic() >= deadline:
                    break

                # Exponential backoff with jitter to avoid thundering herd
                base = self.config.poll_interval_seconds
                raw_delay = min(base * (2 ** attempt), self.config.max_poll_interval_seconds)
                jittered_delay = raw_delay * (0.5 + random.random() * 0.5)
                time.sleep(jittered_delay)
                attempt += 1

            # Timeout reached.
            logger.warning(
                "Approval hold timed out for approval_id=%s; applying timeout_behavior=%s",
                approval_id, self.config.timeout_behavior,
            )
            timeout_decision = _normalize_decision(self.config.timeout_behavior)
            if timeout_decision == "approved":
                _do_resume()
            else:
                # Denied: do NOT resume — enforcer will kill.
                # Clear suspended_pids so the finally block doesn't resume.
                suspended_pids = set()
            return HoldResult(
                decision=timeout_decision,
                approval_id=approval_id,
                timed_out=True,
                hold_effective=_hold_effective,
            )
        finally:
            # Safety net: if we exit due to an unexpected exception, always resume
            # any still-suspended processes so they aren't left frozen indefinitely.
            if suspended_pids:
                logger.warning(
                    "Exception path: resuming %d suspended PIDs in finally block",
                    len(suspended_pids),
                )
                _do_resume()
