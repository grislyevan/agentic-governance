"""Approval hold manager: posts ApprovalRequest to server, polls for decision.

Two usage modes:

Synchronous (legacy, deprecated):
    ``ApprovalHoldManager.wait_for_decision()`` blocks the calling thread until
    a decision arrives or the timeout expires.  This stalls the scan cycle and
    should be avoided in daemon mode.

Asynchronous (recommended for daemon mode):
    ``AsyncApprovalHoldManager.submit_hold()`` returns immediately after posting
    the approval request.  A background ``HoldResolutionThread`` polls pending
    holds and fires registered callbacks when a decision arrives.

    Usage::

        mgr = AsyncApprovalHoldManager(api_url, api_key, config)
        mgr.start()   # start background thread (idempotent)
        mgr.submit_hold(
            event_id=..., tool_name=..., ...,
            on_approved=lambda hold_id: ...,
            on_denied=lambda hold_id: ...,
        )
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)


@dataclass
class HoldConfig:
    poll_interval_seconds: int = 10
    max_poll_interval_seconds: int = 60
    timeout_seconds: int = 300
    timeout_behavior: str = "deny"  # "deny" | "approve"
    offline_behavior: str = "deny"  # "deny" | "approve"

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
    decision: str  # "approved" | "denied"
    approval_id: str | None
    timed_out: bool = False
    hold_effective: bool = (
        False  # True when at least one PID was successfully SIGSTOP'd
    )


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

    def __init__(
        self, api_url: str, api_key: str, config: HoldConfig | None = None
    ) -> None:
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
                resp.status_code,
                approval_id,
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
                        len(suspended_pids),
                        len(pids),
                        max_suspend_seconds,
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
                event_id,
                self.config.offline_behavior,
            )
            return HoldResult(
                decision=_normalize_decision(self.config.offline_behavior),
                approval_id=None,
            )

        logger.info(
            "Approval hold started: approval_id=%s event_id=%s tool=%s",
            approval_id,
            event_id,
            tool_name,
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
                            len(suspended_pids),
                            max_suspend_seconds,
                        )
                        _do_resume()

                try:
                    status = self._poll_decision(approval_id)
                except requests.exceptions.RequestException:
                    logger.warning(
                        "Poll failed for approval %s; retrying with backoff",
                        approval_id,
                    )
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
                        logger.info(
                            "Approval decision: approved for approval_id=%s",
                            approval_id,
                        )
                        _do_resume()
                        return HoldResult(
                            decision="approved",
                            approval_id=approval_id,
                            hold_effective=_hold_effective,
                        )
                    if status == "denied":
                        logger.info(
                            "Approval decision: denied for approval_id=%s", approval_id
                        )
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
                raw_delay = min(
                    base * (2**attempt), self.config.max_poll_interval_seconds
                )
                jittered_delay = raw_delay * (0.5 + random.random() * 0.5)
                time.sleep(jittered_delay)
                attempt += 1

            # Timeout reached.
            logger.warning(
                "Approval hold timed out for approval_id=%s; applying timeout_behavior=%s",
                approval_id,
                self.config.timeout_behavior,
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


# ---------------------------------------------------------------------------
# Async hold: non-blocking submission + background resolution thread
# ---------------------------------------------------------------------------


@dataclass
class _PendingHold:
    """Internal state for one in-flight async approval hold."""

    approval_id: str
    event_id: str
    tool_name: str
    deadline: float  # monotonic timestamp
    on_approved: Callable[[str], None] | None
    on_denied: Callable[[str], None] | None
    attempt: int = 0
    next_poll_at: float = field(default_factory=time.monotonic)
    timed_out: bool = False


class AsyncApprovalHoldManager:
    """Non-blocking approval hold manager for daemon-mode use.

    ``submit_hold()`` returns immediately after posting the approval request to
    the server.  A background ``HoldResolutionThread`` polls all pending holds
    at configurable intervals and fires ``on_approved`` / ``on_denied``
    callbacks when a decision arrives.

    The scan cycle is *never* blocked.

    Thread safety: all pending-hold state is protected by a ``threading.Lock``.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        config: HoldConfig | None = None,
        *,
        resolution_poll_seconds: float = 5.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self.config = config or HoldConfig()
        self._resolution_poll_seconds = resolution_poll_seconds

        self._lock = threading.Lock()
        self._pending: dict[str, _PendingHold] = {}  # keyed by approval_id
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # -- Lifecycle -------------------------------------------------------------

    def start(self) -> None:
        """Start the background resolution thread (idempotent)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._resolution_loop,
                name="hold-resolution",
                daemon=True,
            )
            self._thread.start()
            logger.debug("AsyncApprovalHoldManager: background thread started")

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    # -- Submit ----------------------------------------------------------------

    def submit_hold(
        self,
        event_id: str,
        tool_name: str,
        tool_class: str,
        confidence_band: str,
        confidence_score: float,
        policy_rule_id: str,
        endpoint_id: str | None = None,
        *,
        on_approved: Callable[[str], None] | None = None,
        on_denied: Callable[[str], None] | None = None,
    ) -> str | None:
        """Post an approval request and register callbacks.  Returns approval_id or None.

        Returns immediately — does *not* block the scan cycle.
        The background thread will fire ``on_approved`` or ``on_denied`` when a
        decision arrives (or the hold times out).
        """
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

        try:
            resp = requests.post(
                f"{self._api_url}/approvals",
                json=payload,
                headers={
                    "X-Api-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            approval_id = resp.json()["id"]
        except Exception:
            logger.warning(
                "AsyncApprovalHoldManager: failed to submit hold for event %s (offline?); "
                "applying offline_behavior=%s",
                event_id,
                self.config.offline_behavior,
            )
            # Fire the appropriate callback immediately on offline failure
            decision = _normalize_decision(self.config.offline_behavior)
            if decision == "approved" and on_approved:
                try:
                    on_approved("")
                except Exception:
                    logger.exception(
                        "on_approved callback raised during offline fallback"
                    )
            elif decision == "denied" and on_denied:
                try:
                    on_denied("")
                except Exception:
                    logger.exception(
                        "on_denied callback raised during offline fallback"
                    )
            return None

        now = time.monotonic()
        hold = _PendingHold(
            approval_id=approval_id,
            event_id=event_id,
            tool_name=tool_name,
            deadline=now + self.config.timeout_seconds,
            on_approved=on_approved,
            on_denied=on_denied,
            next_poll_at=now,  # poll immediately on first resolution loop tick
        )
        with self._lock:
            self._pending[approval_id] = hold

        logger.info(
            "AsyncApprovalHoldManager: hold submitted approval_id=%s event_id=%s tool=%s",
            approval_id,
            event_id,
            tool_name,
        )
        return approval_id

    @property
    def pending_count(self) -> int:
        """Number of in-flight holds waiting for a decision."""
        with self._lock:
            return len(self._pending)

    # -- Background resolution loop --------------------------------------------

    def _resolution_loop(self) -> None:
        """Continuously poll pending holds and fire callbacks on decisions."""
        while not self._stop_event.is_set():
            now = time.monotonic()
            to_resolve: list[_PendingHold] = []

            with self._lock:
                for hold in list(self._pending.values()):
                    if now >= hold.next_poll_at:
                        to_resolve.append(hold)

            for hold in to_resolve:
                self._tick_hold(hold)

            self._stop_event.wait(timeout=self._resolution_poll_seconds)

    def _tick_hold(self, hold: _PendingHold) -> None:
        """Check one hold for a decision; update state or fire callbacks."""
        now = time.monotonic()

        # Timeout check
        if now >= hold.deadline:
            logger.warning(
                "AsyncApprovalHoldManager: hold timed out approval_id=%s; applying timeout_behavior=%s",
                hold.approval_id,
                self.config.timeout_behavior,
            )
            decision = _normalize_decision(self.config.timeout_behavior)
            self._resolve(hold, decision, timed_out=True)
            return

        # Poll for decision
        try:
            resp = requests.get(
                f"{self._api_url}/approvals/{hold.approval_id}",
                headers={
                    "X-Api-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code in (401, 403, 404):
                logger.warning(
                    "AsyncApprovalHoldManager: non-transient HTTP %s for approval_id=%s; denying",
                    resp.status_code,
                    hold.approval_id,
                )
                self._resolve(hold, "denied")
                return
            resp.raise_for_status()
            status = resp.json().get("status", "pending")
        except requests.exceptions.RequestException:
            logger.debug(
                "AsyncApprovalHoldManager: poll failed for approval_id=%s; will retry",
                hold.approval_id,
            )
            status = "pending"

        if status == "approved":
            logger.info(
                "AsyncApprovalHoldManager: approved approval_id=%s", hold.approval_id
            )
            self._resolve(hold, "approved")
            return
        if status == "denied":
            logger.info(
                "AsyncApprovalHoldManager: denied approval_id=%s", hold.approval_id
            )
            self._resolve(hold, "denied")
            return

        # Still pending — schedule next poll with exponential backoff + jitter
        base = self.config.poll_interval_seconds
        raw_delay = min(base * (2**hold.attempt), self.config.max_poll_interval_seconds)
        jitter = raw_delay * (0.5 + random.random() * 0.5)
        with self._lock:
            if hold.approval_id in self._pending:
                hold.attempt += 1
                hold.next_poll_at = time.monotonic() + jitter

    def _resolve(
        self,
        hold: _PendingHold,
        decision: str,
        *,
        timed_out: bool = False,
    ) -> None:
        """Remove hold from pending map and fire the appropriate callback."""
        with self._lock:
            self._pending.pop(hold.approval_id, None)

        callback = hold.on_approved if decision == "approved" else hold.on_denied
        if callback:
            try:
                callback(hold.approval_id)
            except Exception:
                logger.exception(
                    "AsyncApprovalHoldManager: callback raised for approval_id=%s decision=%s",
                    hold.approval_id,
                    decision,
                )
