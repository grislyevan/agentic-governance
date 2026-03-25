"""Approval hold manager: posts ApprovalRequest to server, polls for decision."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class HoldConfig:
    poll_interval_seconds: int = 10
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
            timeout_seconds=int(d.get("timeout_seconds", 300)),
            timeout_behavior=d.get("timeout_behavior", "deny"),
            offline_behavior=d.get("offline_behavior", "deny"),
        )


@dataclass
class HoldResult:
    decision: str           # "approved" | "denied"
    approval_id: str | None
    timed_out: bool = False


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
    ) -> HoldResult:
        """Block until an approval decision arrives or timeout expires."""
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

        deadline = time.monotonic() + self.config.timeout_seconds
        while True:
            try:
                status = self._poll_decision(approval_id)
            except requests.exceptions.RequestException:
                logger.warning("Poll failed for approval %s; retrying", approval_id)
            else:
                if status is None:
                    # Non-transient HTTP error — fail fast
                    return HoldResult(decision="denied", approval_id=approval_id)
                if status in ("approved", "denied"):
                    logger.info("Approval decision: %s for approval_id=%s", status, approval_id)
                    return HoldResult(decision=status, approval_id=approval_id)

            if time.monotonic() >= deadline:
                break
            time.sleep(self.config.poll_interval_seconds)

        logger.warning(
            "Approval hold timed out for approval_id=%s; applying timeout_behavior=%s",
            approval_id, self.config.timeout_behavior,
        )
        return HoldResult(
            decision=_normalize_decision(self.config.timeout_behavior),
            approval_id=approval_id,
            timed_out=True,
        )
