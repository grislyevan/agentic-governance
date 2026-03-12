"""Data flow router: AI tool network destination visibility.

Aggregates LLM API destination data from event payloads to show
which AI services endpoints are communicating with and how often.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.tenant import resolve_auth

router = APIRouter(prefix="/data-flow", tags=["data-flow"])

_LLM_PROVIDER_LABELS: dict[str, str] = {
    "api.openai.com": "OpenAI",
    "api.anthropic.com": "Anthropic",
    "generativelanguage.googleapis.com": "Google (Gemini)",
    "api.groq.com": "Groq",
    "api.mistral.ai": "Mistral",
    "api.cohere.ai": "Cohere",
    "api.together.xyz": "Together AI",
    "api.replicate.com": "Replicate",
    "api.deepseek.com": "DeepSeek",
    "api.fireworks.ai": "Fireworks AI",
    "localhost:11434": "Ollama (local)",
    "localhost:1234": "LM Studio (local)",
    "127.0.0.1:8080": "Local LLM",
}


def _extract_destinations(payload: dict[str, Any]) -> list[str]:
    """Pull LLM destination hosts from an event payload's evidence."""
    hosts: list[str] = []

    evidence = payload.get("action", {}).get("raw_ref", "")

    # Behavioral scanner stores BEH-002 evidence inside behavioral_patterns
    for bp in (payload.get("evidence", {}).get("behavioral_patterns", [])
               + payload.get("action", {}).get("behavioral_patterns", [])):
        ev = bp.get("evidence", {})
        for h in ev.get("unique_hosts", []):
            if h and h not in hosts:
                hosts.append(h)

    # Some scanners store connection info directly
    for key in ("connections", "network_connections", "llm_connections",
                "cursor_tls_connections"):
        for conn in payload.get("evidence", {}).get(key, []):
            dest = conn.get("remote_address") or conn.get("dest") or conn.get("host") or ""
            host = dest.split(":")[0] if dest else ""
            if host and host not in hosts:
                hosts.append(host)

    return hosts


@router.get("/summary")
def data_flow_summary(
    days: int = Query(default=7, ge=1, le=90),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate AI data flow destinations across all endpoints."""
    from models.event import Event

    auth = resolve_auth(authorization, x_api_key, db)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    events = (
        db.query(Event)
        .filter(
            Event.tenant_id == auth.tenant_id,
            Event.observed_at >= since,
            Event.event_type == "detection.observed",
        )
        .all()
    )

    dest_counts: dict[str, int] = {}
    dest_endpoints: dict[str, set[str]] = {}
    dest_tools: dict[str, set[str]] = {}
    total_connections = 0

    for ev in events:
        payload = ev.payload or {}
        hosts = _extract_destinations(payload)
        tool_name = ev.tool_name or "unknown"
        ep_id = ev.endpoint_id or "unknown"

        for host in hosts:
            dest_counts[host] = dest_counts.get(host, 0) + 1
            total_connections += 1
            if host not in dest_endpoints:
                dest_endpoints[host] = set()
            dest_endpoints[host].add(ep_id)
            if host not in dest_tools:
                dest_tools[host] = set()
            dest_tools[host].add(tool_name)

    destinations = []
    for host, count in sorted(dest_counts.items(), key=lambda x: -x[1]):
        destinations.append({
            "host": host,
            "provider": _LLM_PROVIDER_LABELS.get(host, host),
            "request_count": count,
            "endpoint_count": len(dest_endpoints.get(host, set())),
            "tools": sorted(dest_tools.get(host, set())),
        })

    local_count = sum(
        d["request_count"] for d in destinations
        if d["host"].startswith("localhost") or d["host"].startswith("127.")
    )
    cloud_count = total_connections - local_count

    return {
        "period_days": days,
        "total_connections": total_connections,
        "unique_destinations": len(destinations),
        "local_llm_connections": local_count,
        "cloud_llm_connections": cloud_count,
        "destinations": destinations,
    }
