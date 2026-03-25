"""Prometheus metrics for the Detec API."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

detec_events_ingested_total = Counter(
    "detec_events_ingested_total",
    "Total events ingested via HTTP or TCP",
)

detec_active_connections = Gauge(
    "detec_active_connections",
    "Number of active TCP gateway connections",
)

detec_enforcement_actions_total = Counter(
    "detec_enforcement_actions_total",
    "Total enforcement actions",
    ["action", "result"],
)

detec_audit_write_failures_total = Counter(
    "detec_audit_write_failures_total",
    "Total audit log write failures (fail-open; request continues)",
)

# Gateway/protocol error taxonomy for pilot observability (see docs/pilot-runbook.md).
detec_gateway_decode_errors_total = Counter(
    "detec_gateway_decode_errors_total",
    "Total gateway frame decode errors (malformed or oversized frame)",
)
detec_gateway_handler_errors_total = Counter(
    "detec_gateway_handler_errors_total",
    "Total gateway message handler errors (per-message; session continues)",
)
detec_gateway_db_errors_total = Counter(
    "detec_gateway_db_errors_total",
    "Total gateway database errors (auth, ingest, heartbeat)",
)
detec_gateway_transport_errors_total = Counter(
    "detec_gateway_transport_errors_total",
    "Total gateway transport/session errors (connection lost, session crash)",
)
detec_gateway_webhook_errors_total = Counter(
    "detec_gateway_webhook_errors_total",
    "Total webhook dispatch failures during event ingest (fail-open; event still stored)",
)
detec_http_webhook_errors_total = Counter(
    "detec_http_webhook_errors_total",
    "Total webhook dispatch failures in HTTP ingest path (fail-open; event still stored)",
)

# Playbook/orchestrator runtime observability.
detec_playbook_runs_total = Counter(
    "detec_playbook_runs_total",
    "Total playbook background task runs queued",
)
detec_playbook_run_outcomes_total = Counter(
    "detec_playbook_run_outcomes_total",
    "Playbook background run outcomes",
    ["result"],  # success|failure
)
detec_playbook_run_latency_seconds = Histogram(
    "detec_playbook_run_latency_seconds",
    "Playbook background run latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Behavioral detection observability.
detec_bg_task_failures_total = Counter(
    "detec_bg_task_failures_total",
    "Total background task loop failures",
    ["task"],
)

detec_beh009_hits_total = Counter(
    "detec_beh009_hits_total",
    "Count of ingested events containing BEH-009 / DETEC-BEH-CORE-04",
)
detec_beh009_chain_kind_total = Counter(
    "detec_beh009_chain_kind_total",
    "Composition of BEH-009 chain terminal action",
    ["kind"],  # file_write|git_add|git_commit|other
)


# Agent telemetry pressure metrics — updated on event ingest when agent_status is present
detec_agent_avg_scan_ms = Gauge(
    "detec_agent_avg_scan_ms",
    "Rolling average scan duration in milliseconds reported by agent (last received value per endpoint)",
    ["endpoint_id"],
)

detec_agent_events_in_store = Gauge(
    "detec_agent_events_in_store",
    "Total events in agent event store (sum across types, last received value per endpoint)",
    ["endpoint_id"],
)

detec_agent_capability_drift_total = Counter(
    "detec_agent_capability_drift_total",
    "Total capability drift incidents reported by agents (a previously-present telemetry capability disappeared)",
    ["endpoint_id", "capability"],
)


def get_metrics() -> bytes:
    return generate_latest()
