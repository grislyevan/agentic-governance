"""Events router: ingest and query canonical detection events."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel
from sqlalchemy import desc, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.database import engine
from core.metrics import (
    detec_events_ingested_total,
    detec_http_webhook_errors_total,
    detec_beh009_hits_total,
    detec_beh009_chain_kind_total,
    detec_agent_avg_scan_ms,
    detec_agent_events_in_store,
    detec_agent_capability_drift_total,
)
from core.rate_limit import limiter
from core.database import get_db
from core.event_validator import validate_event_payload
from core.retention import purge_tenant_events
from core.auth_cookies import get_authorization
from core.tenant import (
    get_tenant_id as _get_tenant_id,
    resolve_auth,
    get_tenant_filter,
    strict_tenant_filter,
    require_role,
)
from models.endpoint import Endpoint
from models.event import Event
from schemas.events import EventIngest, EventListResponse, EventResponse
from webhooks.dispatcher import dispatch_event as _dispatch_webhooks

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

router = APIRouter(prefix="/events", tags=["events"])


def _get_or_create_endpoint(
    tenant_id: str, endpoint_data: dict[str, Any] | None, db: Session
) -> str | None:
    if not endpoint_data:
        return None
    hostname = endpoint_data.get("id") or endpoint_data.get("hostname", "unknown")
    ep = (
        db.query(Endpoint)
        .filter(Endpoint.tenant_id == tenant_id, Endpoint.hostname == hostname)
        .first()
    )
    if not ep:
        ep = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            hostname=hostname,
            os_info=endpoint_data.get("os"),
            management_state=endpoint_data.get(
                "management_state", endpoint_data.get("posture", "unmanaged")
            ),
        )
        db.add(ep)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            ep = (
                db.query(Endpoint)
                .filter(Endpoint.tenant_id == tenant_id, Endpoint.hostname == hostname)
                .first()
            )
            if ep is None:
                return None  # caller handles None
    ep.last_seen_at = datetime.now(timezone.utc)
    return ep.id


def _verify_signature(body: EventIngest, db: Session, tenant_id: str) -> bool | None:
    """Verify the Ed25519 signature on an incoming event.

    Returns True if valid, False if invalid, None if unsigned or
    crypto is unavailable.
    """
    sig_hex = body.signature
    fingerprint = body.key_fingerprint
    if not sig_hex or not fingerprint or not _HAS_CRYPTO:
        return None

    ep = (
        db.query(Endpoint)
        .filter(
            Endpoint.tenant_id == tenant_id,
            Endpoint.key_fingerprint == fingerprint,
        )
        .first()
    )
    if ep is None or ep.signing_public_key is None:
        logger.warning("Signature from unknown fingerprint %s", fingerprint)
        return False

    try:
        pub_key = load_pem_public_key(ep.signing_public_key.encode())
        if not isinstance(pub_key, Ed25519PublicKey):
            return False

        event_dict = body.model_dump(exclude={"signature", "key_fingerprint"})
        filtered = {k: v for k, v in event_dict.items() if v is not None}
        canonical = json.dumps(
            filtered, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        sig_bytes = bytes.fromhex(sig_hex)
        pub_key.verify(sig_bytes, canonical)
        return True
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Signature verification failed for fingerprint %s: %s", fingerprint, exc
        )
        return False
    except Exception as exc:
        logger.exception(
            "Unexpected %s during signature verification for fingerprint %s",
            type(exc).__name__,
            fingerprint,
        )
        return False


def _record_beh009_metrics(event_payload: dict[str, Any]) -> None:
    """Record BEH-009 observability metrics from ingested event payload."""
    try:
        evidence = event_payload.get("evidence_details") or {}
        patterns = evidence.get("behavioral_patterns") or []
        for p in patterns:
            if p.get("pattern_id") != "BEH-009":
                continue
            detec_beh009_hits_total.inc()
            ev = p.get("evidence") or {}
            file_kind = str(ev.get("file_kind") or "other")
            if file_kind == "file write":
                detec_beh009_chain_kind_total.labels(kind="file_write").inc()
            elif file_kind == "git add":
                detec_beh009_chain_kind_total.labels(kind="git_add").inc()
            elif file_kind == "git commit":
                detec_beh009_chain_kind_total.labels(kind="git_commit").inc()
            else:
                detec_beh009_chain_kind_total.labels(kind="other").inc()
            break
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        logger.warning("BEH-009 metric recording failed: %s", exc)
    except Exception as exc:
        logger.exception(
            "Unexpected %s in BEH-009 metric recording", type(exc).__name__
        )


def _record_agent_telemetry_metrics(
    event_payload: dict[str, Any], endpoint_id: str | None
) -> None:
    """Update Prometheus gauges from agent_status in event payload (additive, fail-open)."""
    try:
        agent_status = event_payload.get("agent_status")
        if not agent_status:
            return
        eid = endpoint_id or "unknown"

        avg_scan_ms = agent_status.get("avg_scan_ms")
        if avg_scan_ms is not None:
            detec_agent_avg_scan_ms.labels(endpoint_id=eid).set(float(avg_scan_ms))

        events_in_store = agent_status.get("events_in_store")
        if events_in_store is not None:
            total = (
                sum(events_in_store.values())
                if isinstance(events_in_store, dict)
                else events_in_store
            )
            detec_agent_events_in_store.labels(endpoint_id=eid).set(float(total))

        capability_drift = agent_status.get("capability_drift") or []
        for cap in capability_drift:
            detec_agent_capability_drift_total.labels(
                endpoint_id=eid, capability=str(cap)
            ).inc()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        logger.warning("Agent telemetry metric recording failed: %s", exc)
    except Exception as exc:
        logger.exception(
            "Unexpected %s in agent telemetry metric recording", type(exc).__name__
        )


async def _run_edr_enforcement(
    tenant_id: str, endpoint_id: str | None, event_payload: dict[str, object]
) -> None:
    """Background task: delegate enforcement to EDR if configured."""
    from core.config import settings as _settings

    if not _settings.edr_enforcement_configured or not endpoint_id:
        return

    enforcement = event_payload.get("enforcement") or {}
    policy = event_payload.get("policy") or {}
    decision = policy.get("decision_state", "")
    if decision != "block":
        return

    from core.database import SessionLocal
    from integrations import enforcement_router as enf_router

    db = SessionLocal()
    try:
        ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
        if not ep or not ep.enforcement_provider:
            return

        action = enforcement.get("action", "kill_process")
        pid = enforcement.get("pid")
        process_name = enforcement.get("process_name")

        await enf_router.enforce(
            db=db,
            tenant_id=tenant_id,
            endpoint_id=endpoint_id,
            hostname=ep.hostname,
            enforcement_provider_name=ep.enforcement_provider,
            action=action,
            pid=pid,
            process_name=process_name,
        )
        db.commit()
    except (ConnectionError, OSError, TimeoutError) as exc:
        logger.warning(
            "EDR enforcement network error for event %s: %s",
            event_payload.get("event_id"),
            exc,
        )
    except Exception as exc:
        logger.exception(
            "EDR enforcement failed (%s) for event %s",
            type(exc).__name__,
            event_payload.get("event_id"),
        )
    finally:
        db.close()


async def _run_edr_enrichment(event_payload: dict[str, object]) -> None:
    """Background task: run EDR enrichment and persist confidence updates.

    When enrichment raises the confidence band (e.g. Medium → High), the
    ``Event.attribution_confidence`` column is updated in-place and an
    ``enrichment.applied`` audit record is written so the change is auditable.
    """
    from core.config import settings as _settings

    if not _settings.edr_enrichment_enabled or not _settings.edr_configured:
        return
    if event_payload.get("event_type") != "detection.observed":
        return

    try:
        from integrations.enrichment import enrich_detection
        from integrations.crowdstrike import CrowdStrikeProvider

        if _settings.edr_provider.lower() != "crowdstrike":
            return
        provider = CrowdStrikeProvider(
            api_base=_settings.edr_api_base,
            client_id=_settings.edr_client_id,
            client_secret=_settings.edr_client_secret,
        )
        result = await enrich_detection(
            event_payload=event_payload,
            provider=provider,
            settings=_settings,
        )
        if result is None:
            return

        logger.info(
            "EDR enrichment for event %s: %.4f -> %.4f (band_changed=%s, penalties_removed=%s)",
            event_payload.get("event_id"),
            result.original_confidence,
            result.enriched_confidence,
            result.band_changed,
            result.penalties_removed,
        )

        # Always persist the enriched confidence score; write an audit record
        # when the band changes so analysts can see the EDR-driven rescore.
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            event_id_val = event_payload.get("event_id")
            ev_row = db.query(Event).filter(Event.event_id == event_id_val).first()
            if ev_row is not None:
                ev_row.attribution_confidence = result.enriched_confidence
                # Embed enrichment metadata into the payload JSON for future reads
                payload_copy = dict(ev_row.payload or {})
                payload_copy["edr_enrichment"] = {
                    "provider": result.provider,
                    "original_confidence": result.original_confidence,
                    "enriched_confidence": result.enriched_confidence,
                    "band_changed": result.band_changed,
                    "penalties_removed": result.penalties_removed,
                    "process_events_matched": result.process_events_matched,
                    "network_events_matched": result.network_events_matched,
                    "file_events_matched": result.file_events_matched,
                }
                ev_row.payload = payload_copy
                db.commit()

                if result.band_changed:
                    audit_record(
                        db,
                        tenant_id=ev_row.tenant_id,
                        actor_id=None,
                        actor_type="system",
                        action="enrichment.applied",
                        resource_type="event",
                        resource_id=str(ev_row.id),
                        detail={
                            "provider": result.provider,
                            "original_confidence": result.original_confidence,
                            "enriched_confidence": result.enriched_confidence,
                            "penalties_removed": result.penalties_removed,
                        },
                    )
                    db.commit()
                    logger.info(
                        "EDR enrichment applied: confidence band changed for event %s",
                        event_id_val,
                    )
        finally:
            db.close()

    except (ConnectionError, OSError, TimeoutError) as exc:
        logger.warning(
            "EDR enrichment network error for event %s: %s",
            event_payload.get("event_id"),
            exc,
        )
    except ImportError:
        logger.warning(
            "EDR enrichment import failed for event %s (missing dependency)",
            event_payload.get("event_id"),
        )
    except Exception as exc:
        logger.exception(
            "EDR enrichment failed (%s) for event %s",
            type(exc).__name__,
            event_payload.get("event_id"),
        )


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("120/minute")
def ingest_event(
    request: Request,
    body: EventIngest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EventResponse:
    """Ingest a single canonical event from the collector agent.

    If the event carries ``_signature`` and ``_key_fingerprint``, the
    server verifies the Ed25519 signature against the enrolled public
    key.  Events with invalid signatures are rejected with 403.
    """
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    validation_errors = validate_event_payload(
        body.model_dump(mode="json", exclude_none=True)
    )
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Event validation failed: {'; '.join(validation_errors)}",
        )

    existing = (
        db.query(Event)
        .filter(
            Event.event_id == body.event_id,
            Event.tenant_id == tenant_id,
        )
        .first()
    )
    if existing:
        return EventResponse.model_validate(existing)

    sig_verified = _verify_signature(body, db, tenant_id)
    if sig_verified is False:
        logger.warning(
            "Rejected event %s: signature verification failed", body.event_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Event signature verification failed",
        )

    # Enrolled endpoints must sign their events
    ep_data = body.endpoint or {}
    ep_hostname = ep_data.get("id") or ep_data.get("hostname")
    if sig_verified is None and ep_hostname and _HAS_CRYPTO:
        enrolled_ep = (
            db.query(Endpoint)
            .filter(
                Endpoint.tenant_id == tenant_id,
                Endpoint.hostname == ep_hostname,
                Endpoint.signing_public_key.isnot(None),
            )
            .first()
        )
        if enrolled_ep is not None:
            logger.warning(
                "Rejected unsigned event %s from enrolled endpoint %s",
                body.event_id,
                ep_hostname,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enrolled endpoints must sign events",
            )

    endpoint_id = _get_or_create_endpoint(tenant_id, body.endpoint, db)
    if endpoint_id is None and body.endpoint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Endpoint registration conflict, retry",
        )

    tool = body.tool or {}
    policy = body.policy or {}
    severity = body.severity or {}

    attribution_sources = tool.get("attribution_sources")
    if isinstance(attribution_sources, list):
        attribution_sources = ",".join(attribution_sources)

    event = Event(
        id=str(uuid.uuid4()),
        event_id=body.event_id,
        tenant_id=tenant_id,
        endpoint_id=endpoint_id,
        event_type=body.event_type,
        event_version=body.event_version,
        observed_at=body.observed_at,
        session_id=body.session_id,
        trace_id=body.trace_id,
        parent_event_id=body.parent_event_id,
        tool_name=tool.get("name"),
        tool_class=tool.get("class"),
        tool_version=tool.get("version"),
        attribution_confidence=tool.get("attribution_confidence"),
        attribution_sources=attribution_sources,
        decision_state=policy.get("decision_state"),
        rule_id=policy.get("rule_id"),
        severity_level=severity.get("level"),
        signature_verified=sig_verified,
        payload=body.model_dump(mode="json"),
    )
    db.add(event)
    detec_events_ingested_total.inc()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Event)
            .filter(
                Event.event_id == body.event_id,
                Event.tenant_id == tenant_id,
            )
            .first()
        )
        if existing:
            return EventResponse.model_validate(existing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Duplicate event_id"
        )
    db.refresh(event)

    event_type_val = body.event_type
    if event_type_val and (
        event_type_val.startswith("enforcement.") or event_type_val == "posture.changed"
    ):
        detail: dict[str, Any] = {}
        if body.enforcement:
            detail["enforcement"] = body.enforcement
        if body.posture:
            detail["posture"] = body.posture
        audit_record(
            db,
            tenant_id=tenant_id,
            actor_id=None,
            actor_type="agent",
            action=event_type_val,
            resource_type="endpoint",
            resource_id=endpoint_id,
            detail=detail if detail else None,
        )

    event_payload = body.model_dump(mode="json")
    _record_beh009_metrics(event_payload)
    _record_agent_telemetry_metrics(event_payload, endpoint_id)

    try:
        _dispatch_webhooks(db, tenant_id, event_payload)
    except (ConnectionError, OSError, TimeoutError) as exc:
        detec_http_webhook_errors_total.inc()
        logger.warning(
            "Webhook dispatch network error for event %s: %s", body.event_id, exc
        )
    except Exception as exc:
        detec_http_webhook_errors_total.inc()
        logger.exception(
            "Webhook dispatch failed (%s) for event %s",
            type(exc).__name__,
            body.event_id,
        )

    try:
        from core.config import settings as _cfg

        if _cfg.edr_enrichment_enabled and _cfg.edr_configured:
            background_tasks.add_task(
                _run_edr_enrichment,
                event_payload,
            )
    except (ImportError, AttributeError) as exc:
        logger.warning("EDR enrichment hook failed to queue: %s", exc)
    except Exception as exc:
        logger.exception("EDR enrichment hook failed to queue (%s)", type(exc).__name__)

    if event_type_val and event_type_val in (
        "enforcement.applied",
        "enforcement.simulated",
    ):
        background_tasks.add_task(
            _run_edr_enforcement,
            tenant_id,
            endpoint_id,
            event_payload,
        )

    return EventResponse.model_validate(event)


class PurgeRequest(BaseModel):
    older_than_days: int | None = None


class PurgeResponse(BaseModel):
    deleted: int


@router.post("/purge", response_model=PurgeResponse)
def purge_events(
    body: PurgeRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> PurgeResponse:
    """Purge events older than retention period. Owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")
    older = body.older_than_days if body else None
    deleted = purge_tenant_events(db, auth.tenant_id, older_than_days=older)
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="events.purged",
        resource_type="events",
        resource_id=None,
        detail={"deleted": deleted, "older_than_days": older},
    )
    db.commit()
    return PurgeResponse(deleted=deleted)


@router.get("", response_model=EventListResponse)
def list_events(
    event_type: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    tool_class: str | None = Query(default=None),
    decision_state: str | None = Query(default=None),
    endpoint_id: str | None = Query(default=None),
    observed_after: datetime | None = Query(default=None),
    observed_before: datetime | None = Query(default=None),
    mitre_technique: str | None = Query(default=None, max_length=16),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EventListResponse:
    """List events for the authenticated user with optional filtering."""
    auth = resolve_auth(authorization, x_api_key, db)

    q = db.query(Event).filter(get_tenant_filter(auth, Event))

    if event_type:
        q = q.filter(Event.event_type == event_type)
    if tool_name:
        q = q.filter(Event.tool_name == tool_name)
    if tool_class:
        q = q.filter(Event.tool_class == tool_class)
    if decision_state:
        q = q.filter(Event.decision_state == decision_state)
    if endpoint_id:
        q = q.filter(Event.endpoint_id == endpoint_id)
    if observed_after:
        q = q.filter(Event.observed_at >= observed_after)
    if observed_before:
        q = q.filter(Event.observed_at <= observed_before)
    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        q = q.filter(Event.tool_name.ilike(f"%{escaped}%", escape="\\"))

    if mitre_technique:
        tid = mitre_technique.strip()
        if engine.dialect.name == "sqlite":
            q = q.filter(
                text(
                    "EXISTS (SELECT 1 FROM json_each(json_extract(payload, '$.mitre_attack.techniques')) "
                    "WHERE json_extract(value, '$.technique_id') = :tid)"
                ).bindparams(tid=tid)
            )
        else:
            q = q.filter(
                text(
                    "EXISTS (SELECT 1 FROM json_array_elements("
                    "COALESCE(payload->'mitre_attack'->'techniques', '[]'::json)) AS t "
                    "WHERE t->>'technique_id' = :tid)"
                ).bindparams(tid=tid)
            )

    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(desc(Event.observed_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return EventListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventResponse.model_validate(e) for e in items],
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EventResponse:
    """Get a single event by id. Tenant-scoped."""
    auth = resolve_auth(authorization, x_api_key, db)
    event = (
        db.query(Event)
        .filter(
            Event.id == event_id,
            strict_tenant_filter(auth, Event),
        )
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return EventResponse.model_validate(event)


class BlockResponse(BaseModel):
    ok: bool = True
    event_id: str
    enforcement_triggered: bool = False


async def _push_kill_to_agent(
    gateway: Any,
    endpoint_id: str,
    pid: int,
    process_name: str,
    tool_name: str,
) -> None:
    """Best-effort push of kill_process command to a TCP-connected agent."""
    try:
        sent = await gateway.push_kill_process(
            endpoint_id=endpoint_id,
            pid=pid,
            process_name=process_name,
            tool_name=tool_name,
        )
        if sent:
            logger.info(
                "Pushed kill_process command to endpoint %s via TCP (pid=%d, process=%s)",
                endpoint_id,
                pid,
                process_name,
            )
        else:
            logger.warning(
                "Agent for endpoint %s not reachable via TCP; kill_process command not delivered",
                endpoint_id,
            )
    except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
        logger.warning(
            "Could not push kill_process to endpoint %s: %s", endpoint_id, exc
        )
    except Exception:
        logger.exception(
            "Unexpected error pushing kill_process to endpoint %s", endpoint_id
        )


@router.post("/{event_id}/block", response_model=BlockResponse)
def block_event(
    event_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> BlockResponse:
    """Record a one-time admin block for this event and optionally trigger EDR enforcement. Admin or owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    # Mutation path must use strict tenant scoping (BOLA guard).
    event = (
        db.query(Event)
        .filter(
            Event.id == event_id,
            strict_tenant_filter(auth, Event),
        )
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    payload = dict(event.payload) if event.payload else {}
    policy = payload.get("policy") or {}
    policy = dict(policy)
    policy["decision_state"] = "block"
    policy["rule_id"] = "ADMIN-BLOCK-ONCE"
    payload["policy"] = policy
    if not payload.get("enforcement") and event.payload:
        payload["enforcement"] = event.payload.get("enforcement") or {}

    admin_block_id = str(uuid.uuid4())
    admin_block_event = Event(
        id=admin_block_id,
        event_id=admin_block_id,
        tenant_id=event.tenant_id,
        endpoint_id=event.endpoint_id,
        event_type="enforcement.admin_block",
        event_version=event.event_version,
        observed_at=datetime.now(timezone.utc),
        session_id=event.session_id,
        trace_id=event.trace_id,
        parent_event_id=event.event_id,
        tool_name=event.tool_name,
        tool_class=event.tool_class,
        tool_version=event.tool_version,
        attribution_confidence=event.attribution_confidence,
        decision_state="block",
        rule_id="ADMIN-BLOCK-ONCE",
        payload=payload,
    )
    db.add(admin_block_event)
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="events.admin_block",
        resource_type="events",
        resource_id=event_id,
        detail={"one_time": True, "original_event_id": event.event_id},
    )
    db.commit()

    enforcement_triggered = False
    if event.endpoint_id and payload.get("policy", {}).get("decision_state") == "block":
        try:
            background_tasks.add_task(
                _run_edr_enforcement,
                event.tenant_id,
                event.endpoint_id,
                payload,
            )
            enforcement_triggered = True
        except Exception:
            logger.warning(
                "EDR enforcement task not queued for admin block", exc_info=True
            )

        # Also push kill command directly to agent via TCP gateway if connected.
        gateway = getattr(request.app.state, "gateway", None)
        if gateway and event.endpoint_id:
            enforcement_info = payload.get("enforcement") or {}
            pid = enforcement_info.get("pid")
            process_name = enforcement_info.get("process_name", "")
            tool_name = event.tool_name or ""
            if pid is not None:
                try:
                    background_tasks.add_task(
                        _push_kill_to_agent,
                        gateway,
                        event.endpoint_id,
                        int(pid),
                        process_name or "",
                        tool_name,
                    )
                except Exception:
                    logger.warning(
                        "Gateway kill push task not queued for admin block",
                        exc_info=True,
                    )

    return BlockResponse(
        event_id=event_id,
        enforcement_triggered=enforcement_triggered,
    )
