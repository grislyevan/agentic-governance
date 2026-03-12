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


def get_metrics() -> bytes:
    return generate_latest()
