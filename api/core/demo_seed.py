"""Demo data seeder: realistic endpoints, events, and enforcement records.

When DEMO_MODE=true, this module populates a tenant with sample data that
exercises every major dashboard view: detection timeline, policy decisions,
enforcement actions, and posture changes.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.endpoint import Endpoint
from models.event import Event

logger = logging.getLogger(__name__)

EVENT_VERSION = "0.4.0"
DEMO_MARKER = "demo-seed"

# ── Endpoint definitions ─────────────────────────────────────────────

DEMO_ENDPOINTS = [
    {
        "hostname": "demo-mbp-eng01",
        "os_info": "macOS 15.4 Darwin 24.4.0 ARM64",
        "management_state": "managed",
        "enforcement_posture": "active",
        "telemetry_provider": "esf",
    },
    {
        "hostname": "demo-ws-fin02",
        "os_info": "Windows 11 23H2 x86_64",
        "management_state": "managed",
        "enforcement_posture": "audit",
        "telemetry_provider": "etw",
    },
    {
        "hostname": "demo-srv-devops03",
        "os_info": "Ubuntu 24.04.2 LTS x86_64",
        "management_state": "unmanaged",
        "enforcement_posture": "passive",
        "telemetry_provider": "polling",
    },
]

# ── Tool profiles used across events ─────────────────────────────────

TOOL_PROFILES = [
    {"name": "Claude Code", "class": "C", "version": "2.1.59", "confidence": 0.88, "sources": ["process", "file", "network"]},
    {"name": "Cursor", "class": "A", "version": "0.48.7", "confidence": 0.92, "sources": ["process", "file"]},
    {"name": "Ollama", "class": "B", "version": "0.5.13", "confidence": 0.78, "sources": ["process", "network"]},
    {"name": "Aider", "class": "C", "version": "0.72.1", "confidence": 0.71, "sources": ["process", "file", "network"]},
    {"name": "OpenClaw", "class": "D", "version": "0.3.0", "confidence": 0.83, "sources": ["process", "file", "network", "behavior"]},
]

# ── Scenario definitions ─────────────────────────────────────────────
# Each scenario produces 1-3 linked events (detection -> policy -> enforcement).

_SCENARIOS: list[dict] = [
    # --- Routine allowed (ENFORCE-001: detect, low confidence, read-only) ---
    *[
        {
            "tool_idx": ti,
            "endpoint_idx": ei,
            "event_chain": ["detection.observed", "policy.evaluated"],
            "decision": "detect",
            "rule_id": "ENFORCE-001",
            "severity": "S1",
            "action_type": "read",
            "risk_class": "R1",
            "sensitivity": "Tier0",
            "summary": f"Routine scan: {TOOL_PROFILES[ti]['name']} read-only access on non-sensitive path",
        }
        for ti, ei in [(1, 0), (0, 1), (2, 2), (1, 1), (2, 0), (0, 2), (1, 2), (3, 0)]
    ],

    # --- Warn: medium confidence write actions (ENFORCE-002) ---
    *[
        {
            "tool_idx": ti,
            "endpoint_idx": ei,
            "event_chain": ["detection.observed", "policy.evaluated"],
            "decision": "warn",
            "rule_id": "ENFORCE-002",
            "severity": "S2",
            "action_type": "write",
            "risk_class": "R2",
            "sensitivity": "Tier1",
            "summary": f"{TOOL_PROFILES[ti]['name']} scoped file writes in project directory",
        }
        for ti, ei in [(0, 0), (3, 1), (0, 2), (1, 0), (3, 2)]
    ],

    # --- Approval required: high confidence, sensitive target (ENFORCE-004) ---
    {
        "tool_idx": 0,
        "endpoint_idx": 0,
        "event_chain": ["detection.observed", "policy.evaluated", "enforcement.escalated"],
        "decision": "approval_required",
        "rule_id": "ENFORCE-004",
        "severity": "S3",
        "action_type": "exec",
        "risk_class": "R3",
        "sensitivity": "Tier2",
        "summary": "Claude Code attempting shell execution on sensitive engineering host",
    },
    {
        "tool_idx": 4,
        "endpoint_idx": 1,
        "event_chain": ["detection.observed", "policy.evaluated", "enforcement.escalated"],
        "decision": "approval_required",
        "rule_id": "ENFORCE-004",
        "severity": "S3",
        "action_type": "exec",
        "risk_class": "R3",
        "sensitivity": "Tier2",
        "summary": "OpenClaw persistent agent performing network operations on finance workstation",
    },

    # --- Block: Class D or high-risk autonomous action (ENFORCE-005 / ENFORCE-D01) ---
    {
        "tool_idx": 4,
        "endpoint_idx": 2,
        "event_chain": ["detection.observed", "policy.evaluated", "enforcement.applied"],
        "decision": "block",
        "rule_id": "ENFORCE-D01",
        "severity": "S3",
        "action_type": "exec",
        "risk_class": "R4",
        "sensitivity": "Tier1",
        "summary": "OpenClaw Class D autonomous agent blocked on devops server",
        "enforcement": {
            "tactic": "process_kill",
            "success": True,
            "detail": "Killed PIDs [8421, 8422] for OpenClaw autonomous agent",
            "simulated": False,
            "allow_listed": False,
            "pids_killed": [8421, 8422],
            "process_name": "openclaw",
            "provider": "local",
        },
    },
    {
        "tool_idx": 0,
        "endpoint_idx": 0,
        "event_chain": ["detection.observed", "policy.evaluated", "enforcement.applied"],
        "decision": "block",
        "rule_id": "ENFORCE-005",
        "severity": "S4",
        "action_type": "privileged",
        "risk_class": "R4",
        "sensitivity": "Tier3",
        "summary": "Claude Code attempted privileged operation on crown-jewel asset",
        "enforcement": {
            "tactic": "process_kill",
            "success": True,
            "detail": "Killed PID [3901] for claude process accessing /etc/ssh/",
            "simulated": False,
            "allow_listed": False,
            "pids_killed": [3901],
            "process_name": "claude",
            "provider": "local",
        },
    },

    # --- Simulated enforcement (audit posture endpoint) ---
    {
        "tool_idx": 3,
        "endpoint_idx": 1,
        "event_chain": ["detection.observed", "policy.evaluated", "enforcement.simulated"],
        "decision": "block",
        "rule_id": "ENFORCE-003",
        "severity": "S2",
        "action_type": "exec",
        "risk_class": "R3",
        "sensitivity": "Tier1",
        "summary": "Aider broad file modification (simulated block, audit posture)",
        "enforcement": {
            "tactic": "process_kill",
            "success": True,
            "detail": "SIMULATED: Would have killed PID [6102] for aider",
            "simulated": True,
            "allow_listed": False,
            "process_name": "aider",
            "provider": "local",
        },
    },

    # --- Rate-limited enforcement ---
    {
        "tool_idx": 4,
        "endpoint_idx": 2,
        "event_chain": ["detection.observed", "enforcement.rate_limited"],
        "decision": "block",
        "rule_id": "ENFORCE-D01",
        "severity": "S2",
        "action_type": "exec",
        "risk_class": "R3",
        "sensitivity": "Tier1",
        "summary": "OpenClaw enforcement suppressed by rate limiter (3rd attempt in 2 min)",
        "enforcement": {
            "tactic": "log_and_alert",
            "success": True,
            "detail": "Enforcement rate-limited: 3 actions against openclaw in 120s window",
            "simulated": False,
            "allow_listed": False,
            "rate_limited": True,
            "process_name": "openclaw",
            "provider": "local",
        },
    },

    # --- Posture change events ---
    {
        "tool_idx": None,
        "endpoint_idx": 0,
        "event_chain": ["posture.changed"],
        "decision": None,
        "rule_id": None,
        "severity": None,
        "action_type": None,
        "risk_class": None,
        "sensitivity": None,
        "summary": "Enforcement posture changed from passive to active",
    },
    {
        "tool_idx": None,
        "endpoint_idx": 1,
        "event_chain": ["posture.changed"],
        "decision": None,
        "rule_id": None,
        "severity": None,
        "action_type": None,
        "risk_class": None,
        "sensitivity": None,
        "summary": "Enforcement posture changed from passive to audit",
    },

    # --- Attribution updates ---
    {
        "tool_idx": 0,
        "endpoint_idx": 0,
        "event_chain": ["attribution.updated"],
        "decision": None,
        "rule_id": None,
        "severity": None,
        "action_type": None,
        "risk_class": None,
        "sensitivity": None,
        "summary": "Claude Code attribution confidence updated from 0.65 to 0.88 after EDR enrichment",
    },
    {
        "tool_idx": 4,
        "endpoint_idx": 2,
        "event_chain": ["attribution.updated"],
        "decision": None,
        "rule_id": None,
        "severity": None,
        "action_type": None,
        "risk_class": None,
        "sensitivity": None,
        "summary": "OpenClaw reclassified from Class C to Class D after behavioral analysis",
    },

    # --- Heartbeats (one per endpoint) ---
    *[
        {
            "tool_idx": None,
            "endpoint_idx": ei,
            "event_chain": ["heartbeat.received"],
            "decision": None,
            "rule_id": None,
            "severity": None,
            "action_type": None,
            "risk_class": None,
            "sensitivity": None,
            "summary": f"Heartbeat from {DEMO_ENDPOINTS[ei]['hostname']}",
        }
        for ei in range(3)
    ],

    # --- Additional detection variety ---
    {
        "tool_idx": 2,
        "endpoint_idx": 0,
        "event_chain": ["detection.observed", "policy.evaluated"],
        "decision": "detect",
        "rule_id": "NET-001",
        "severity": "S1",
        "action_type": "network",
        "risk_class": "R1",
        "sensitivity": "Tier0",
        "summary": "Ollama local inference: outbound connection to model registry",
    },
    {
        "tool_idx": 1,
        "endpoint_idx": 2,
        "event_chain": ["detection.observed", "policy.evaluated"],
        "decision": "detect",
        "rule_id": "NET-002",
        "severity": "S1",
        "action_type": "network",
        "risk_class": "R2",
        "sensitivity": "Tier1",
        "summary": "Cursor extension phoning home to telemetry endpoint",
    },
]


def _actor_for_endpoint(endpoint_idx: int) -> dict:
    actors = [
        {"id": "jchen@acme.com", "type": "human", "trust_tier": "T2", "identity_confidence": 0.95, "org_context": "org"},
        {"id": "mwilson@acme.com", "type": "human", "trust_tier": "T1", "identity_confidence": 0.88, "org_context": "org"},
        {"id": "ci-pipeline@acme.com", "type": "service", "trust_tier": "T2", "identity_confidence": 0.99, "org_context": "org"},
    ]
    return actors[endpoint_idx]


def _build_payload(
    scenario: dict,
    event_type: str,
    event_id: str,
    observed_at: datetime,
    session_id: str,
    trace_id: str,
    parent_event_id: str | None,
    endpoint_info: dict,
) -> dict:
    """Build a canonical event payload matching the v0.4.0 schema."""
    endpoint_idx = scenario["endpoint_idx"]

    payload: dict = {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "observed_at": observed_at.isoformat(),
        "ingested_at": (observed_at + timedelta(seconds=1)).isoformat(),
        "session_id": session_id,
        "trace_id": trace_id,
        "parent_event_id": parent_event_id,
        "actor": _actor_for_endpoint(endpoint_idx),
        "endpoint": endpoint_info,
    }

    tool_idx = scenario.get("tool_idx")
    if tool_idx is not None:
        tp = TOOL_PROFILES[tool_idx]
        payload["tool"] = {
            "name": tp["name"],
            "class": tp["class"],
            "version": tp["version"],
            "attribution_confidence": tp["confidence"],
            "attribution_sources": tp["sources"],
        }

    if scenario.get("action_type") and event_type in (
        "detection.observed", "policy.evaluated",
        "enforcement.applied", "enforcement.simulated",
        "enforcement.escalated",
    ):
        payload["action"] = {
            "type": scenario["action_type"],
            "risk_class": scenario["risk_class"],
            "summary": scenario["summary"],
            "raw_ref": f"evidence://demo-seed/{session_id}/{event_type}",
        }
        payload["target"] = {
            "type": "host",
            "id": DEMO_ENDPOINTS[endpoint_idx]["hostname"],
            "scope": "local endpoint",
            "sensitivity_tier": scenario["sensitivity"],
        }

    if scenario.get("decision") and event_type in (
        "policy.evaluated", "enforcement.applied",
        "enforcement.simulated", "enforcement.escalated",
    ):
        tp = TOOL_PROFILES[tool_idx] if tool_idx is not None else None
        payload["policy"] = {
            "decision_state": scenario["decision"],
            "rule_id": scenario["rule_id"],
            "rule_version": EVENT_VERSION,
            "reason_codes": [f"demo_{scenario['decision']}_{scenario['rule_id'].lower()}"],
            "decision_confidence": tp["confidence"] if tp else 0.5,
        }

    enforcement_data = scenario.get("enforcement")
    if enforcement_data and event_type in (
        "enforcement.applied", "enforcement.simulated",
        "enforcement.rate_limited", "enforcement.escalated",
    ):
        payload["enforcement"] = enforcement_data

    if event_type in (
        "enforcement.applied", "enforcement.simulated",
        "enforcement.rate_limited", "enforcement.escalated",
    ):
        payload["outcome"] = {
            "enforcement_result": "denied" if scenario.get("decision") == "block" else "allowed",
            "incident_flag": False,
            "incident_id": None,
        }

    if scenario.get("severity"):
        payload["severity"] = {"level": scenario["severity"]}

    if event_type == "posture.changed":
        old, new = ("passive", "active") if endpoint_idx == 0 else ("passive", "audit")
        payload["posture"] = {
            "previous": old,
            "current": new,
            "changed_by": _actor_for_endpoint(endpoint_idx)["id"],
            "reason": scenario["summary"],
        }

    if event_type == "enforcement.escalated" and not enforcement_data:
        payload["enforcement"] = {
            "tactic": "hold_pending_approval",
            "success": True,
            "detail": f"Escalated: {scenario['summary']}",
        }
        payload["outcome"] = {
            "enforcement_result": "pending",
            "incident_flag": False,
            "incident_id": None,
        }

    return payload


def seed_demo_endpoints(db: Session, tenant_id: str) -> list[Endpoint]:
    """Create 3 demo endpoints. Returns created Endpoint objects."""
    now = datetime.now(timezone.utc)
    endpoints = []

    for defn in DEMO_ENDPOINTS:
        existing = (
            db.query(Endpoint)
            .filter(Endpoint.tenant_id == tenant_id, Endpoint.hostname == defn["hostname"])
            .first()
        )
        if existing:
            endpoints.append(existing)
            continue

        ep = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            hostname=defn["hostname"],
            os_info=defn["os_info"],
            management_state=defn["management_state"],
            enforcement_posture=defn["enforcement_posture"],
            telemetry_provider=defn["telemetry_provider"],
            status="active",
            last_seen_at=now - timedelta(minutes=random.randint(1, 30)),
        )
        db.add(ep)
        endpoints.append(ep)

    db.flush()
    return endpoints


def seed_demo_events(
    db: Session,
    tenant_id: str,
    endpoints: list[Endpoint],
) -> int:
    """Generate ~50 canonical events across demo scenarios. Returns event count."""
    now = datetime.now(timezone.utc)
    total = 0

    rng = random.Random(42)
    base_offset = timedelta(days=7)

    for scenario_idx, scenario in enumerate(_SCENARIOS):
        ep_idx = scenario["endpoint_idx"]
        ep = endpoints[ep_idx]
        tool_idx = scenario.get("tool_idx")
        tp = TOOL_PROFILES[tool_idx] if tool_idx is not None else None

        session_id = f"demo-sess-{scenario_idx:03d}"
        trace_id = f"demo-trace-{scenario_idx:03d}"
        parent_id: str | None = None

        scenario_offset = base_offset - timedelta(
            hours=rng.randint(0, 168),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
        )

        endpoint_info = {
            "id": ep.hostname,
            "os": ep.os_info or "",
            "posture": "managed" if ep.management_state == "managed" else "unmanaged",
        }

        for chain_idx, event_type in enumerate(scenario["event_chain"]):
            event_id = str(uuid.uuid4())
            observed_at = now - scenario_offset + timedelta(seconds=chain_idx * 2)

            payload = _build_payload(
                scenario=scenario,
                event_type=event_type,
                event_id=event_id,
                observed_at=observed_at,
                session_id=session_id,
                trace_id=trace_id,
                parent_event_id=parent_id,
                endpoint_info=endpoint_info,
            )

            decision_state = None
            rule_id = None
            severity_level = None
            if "policy" in payload:
                decision_state = payload["policy"]["decision_state"]
                rule_id = payload["policy"]["rule_id"]
            if "severity" in payload:
                severity_level = payload["severity"]["level"]

            evt = Event(
                id=str(uuid.uuid4()),
                event_id=event_id,
                tenant_id=tenant_id,
                endpoint_id=ep.id,
                event_type=event_type,
                event_version=EVENT_VERSION,
                observed_at=observed_at,
                session_id=session_id,
                trace_id=trace_id,
                parent_event_id=parent_id,
                tool_name=tp["name"] if tp else None,
                tool_class=tp["class"] if tp else None,
                tool_version=tp["version"] if tp else None,
                attribution_confidence=tp["confidence"] if tp else None,
                attribution_sources=",".join(tp["sources"]) if tp else None,
                decision_state=decision_state,
                rule_id=rule_id,
                severity_level=severity_level,
                payload=payload,
            )
            db.add(evt)
            parent_id = event_id
            total += 1

    db.flush()
    return total


def clear_demo_data(db: Session, tenant_id: str) -> tuple[int, int]:
    """Remove all demo endpoints and events. Returns (events_deleted, endpoints_deleted)."""
    events_deleted = (
        db.query(Event)
        .filter(Event.tenant_id == tenant_id, Event.session_id.like("demo-sess-%"))
        .delete(synchronize_session="fetch")
    )
    endpoints_deleted = 0
    demo_hostnames = [d["hostname"] for d in DEMO_ENDPOINTS]
    for hostname in demo_hostnames:
        n = (
            db.query(Endpoint)
            .filter(Endpoint.tenant_id == tenant_id, Endpoint.hostname == hostname)
            .delete(synchronize_session="fetch")
        )
        endpoints_deleted += n

    db.flush()
    return events_deleted, endpoints_deleted


def seed_demo_data(db: Session, tenant_id: str) -> tuple[int, int]:
    """Full demo seed: endpoints + events. Returns (endpoint_count, event_count)."""
    endpoints = seed_demo_endpoints(db, tenant_id)
    event_count = seed_demo_events(db, tenant_id, endpoints)
    return len(endpoints), event_count
