"""Enforcement orchestration router (server-side decision engine).

Sits between detection events and enforcement execution. For each
enforcement decision it:

1. Checks whether the endpoint has a delegated enforcement_provider
2. If yes and the provider is reachable: delegates to the EDR
3. If EDR fails (timeout, 409, etc.): falls back per configuration
4. If no EDR configured: lets agent-side enforcement handle it
5. Records every decision in the audit log
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.config import settings

from .enforcement_provider import EnforcementProvider, EnforcementResult

logger = logging.getLogger(__name__)

_providers: dict[str, EnforcementProvider] = {}


def register_provider(provider: EnforcementProvider) -> None:
    """Register an enforcement provider by name."""
    _providers[provider.name] = provider
    logger.info("Registered enforcement provider: %s", provider.name)


def get_provider(name: str) -> EnforcementProvider | None:
    return _providers.get(name)


def registered_providers() -> list[str]:
    return list(_providers.keys())


@dataclass
class EnforcementDecision:
    """Captures the full decision chain for audit."""

    delegated: bool
    provider_name: str | None
    action: str
    success: bool
    fallback_used: bool = False
    fallback_reason: str | None = None
    detail: dict[str, Any] | None = None


async def enforce(
    *,
    db: Session,
    tenant_id: str,
    endpoint_id: str,
    hostname: str,
    enforcement_provider_name: str | None,
    action: str,
    pid: int | None = None,
    process_name: str | None = None,
) -> EnforcementDecision:
    """Execute an enforcement action, delegating to EDR if configured.

    Parameters
    ----------
    action : str
        One of: "kill_process", "block_network", "quarantine_endpoint"
    enforcement_provider_name : str | None
        The provider configured on the endpoint, or None for local.

    Returns
    -------
    EnforcementDecision with full audit trail.
    """

    if not settings.edr_enforcement_enabled or not enforcement_provider_name:
        decision = EnforcementDecision(
            delegated=False,
            provider_name=None,
            action=action,
            success=True,
            detail={"path": "local", "reason": "no_edr_configured"},
        )
        _audit(db, tenant_id, endpoint_id, hostname, decision)
        return decision

    provider = get_provider(enforcement_provider_name)
    if not provider:
        logger.warning(
            "Endpoint %s references unknown provider %s; falling back to local",
            endpoint_id, enforcement_provider_name,
        )
        decision = EnforcementDecision(
            delegated=False,
            provider_name=enforcement_provider_name,
            action=action,
            success=True,
            fallback_used=True,
            fallback_reason="provider_not_registered",
        )
        _audit(db, tenant_id, endpoint_id, hostname, decision)
        return decision

    available = False
    try:
        available = await provider.available_for_endpoint(hostname)
    except Exception as e:
        logger.warning("Provider %s availability check failed: %s", enforcement_provider_name, e)

    if not available:
        return _handle_fallback(
            db, tenant_id, endpoint_id, hostname, action,
            enforcement_provider_name, "endpoint_not_reachable",
        )

    result: EnforcementResult | None = None
    try:
        result = await _dispatch(provider, action, hostname, pid, process_name)
    except Exception as e:
        logger.error("Enforcement dispatch failed: %s", e, exc_info=True)

    if result and result.success:
        decision = EnforcementDecision(
            delegated=True,
            provider_name=enforcement_provider_name,
            action=action,
            success=True,
            detail=result.detail,
        )
        _audit(db, tenant_id, endpoint_id, hostname, decision, "enforcement.delegated")
        return decision

    return _handle_fallback(
        db, tenant_id, endpoint_id, hostname, action,
        enforcement_provider_name,
        result.detail.get("reason", "unknown") if result else "dispatch_exception",
    )


async def _dispatch(
    provider: EnforcementProvider,
    action: str,
    hostname: str,
    pid: int | None,
    process_name: str | None,
) -> EnforcementResult:
    if action == "kill_process":
        if pid is None:
            raise ValueError("kill_process requires a pid")
        return await provider.kill_process(hostname, pid, process_name or "unknown")
    elif action == "block_network":
        return await provider.block_network(hostname)
    elif action == "quarantine_endpoint":
        return await provider.quarantine_endpoint(hostname)
    else:
        raise ValueError(f"Unknown enforcement action: {action}")


def _handle_fallback(
    db: Session,
    tenant_id: str,
    endpoint_id: str,
    hostname: str,
    action: str,
    provider_name: str,
    reason: str,
) -> EnforcementDecision:
    fallback = settings.edr_enforcement_fallback

    if fallback == "local":
        decision = EnforcementDecision(
            delegated=False,
            provider_name=provider_name,
            action=action,
            success=True,
            fallback_used=True,
            fallback_reason=reason,
            detail={"path": "fallback_to_local", "original_provider": provider_name},
        )
        _audit(db, tenant_id, endpoint_id, hostname, decision, "enforcement.fallback_to_local")
        return decision

    decision = EnforcementDecision(
        delegated=False,
        provider_name=provider_name,
        action=action,
        success=False,
        fallback_used=False,
        fallback_reason=reason,
        detail={"path": "no_fallback", "original_provider": provider_name},
    )
    _audit(db, tenant_id, endpoint_id, hostname, decision, "enforcement.delegated_failed")
    return decision


def _audit(
    db: Session,
    tenant_id: str,
    endpoint_id: str,
    hostname: str,
    decision: EnforcementDecision,
    action_override: str | None = None,
) -> None:
    audit_action = action_override or (
        "enforcement.delegated" if decision.delegated else "enforcement.local"
    )
    audit_record(
        db,
        tenant_id=tenant_id,
        actor_id=None,
        actor_type="system",
        action=audit_action,
        resource_type="endpoint",
        resource_id=endpoint_id,
        detail={
            "hostname": hostname,
            "enforcement_action": decision.action,
            "provider": decision.provider_name,
            "delegated": decision.delegated,
            "success": decision.success,
            "fallback_used": decision.fallback_used,
            "fallback_reason": decision.fallback_reason,
            **(decision.detail or {}),
        },
    )
