# Telemetry and performance

This note covers agent telemetry store behavior, scan latency targets, and how to monitor store pressure and capability drift.

## Scan latency

- **Target:** Keep average scan duration (`avg_scan_ms` in `agent_status`) in the **50–100 ms** range under normal load.
- **Monitoring:** Rely on `agent_status.avg_scan_ms` and, once available, `agent_status.events_in_store` to spot regressions or memory pressure.
- If `avg_scan_ms` consistently exceeds the target, consider: reducing EventStore query cost, tuning retention or rate caps, or trimming work per scan (e.g. incremental tree updates in the future).

## Event store and diagnostics

- **EventStore** is a thread-safe ring buffer with configurable `max_events` (and optional per-type limits), retention-based eviction on query, and optional per-type rate caps and burst smoothing.
- **Config:** In `collector.json` (or platform config paths), an optional `event_store` object supports:
  - `max_events` (default 10,000)
  - `retention_seconds` (default 120)
  - `max_events_per_type` (optional): e.g. `{"process": 5000, "network": 2000}`
  - `rate_cap_per_second` (default 0 = disabled): max events per second per type; when exceeded, new events are dropped.
  - `burst_window_seconds`, `max_events_per_burst`: optional burst smoothing (e.g. cap per 100 ms window).
- **Diagnostics:** Each event payload can include `agent_status` with:
  - `events_in_store`: `{"process": N, "network": N, "file": N, "file_read": N}` (post-retention counts) for tuning and alerting.
  - `capability_drift`: list of capability names that were present and then disappeared (e.g. `["file_read", "network_events"]`), with debounce to avoid false positives after provider switch or restart.

## Capability drift

When a telemetry capability that was previously available (e.g. file read events, network events) disappears, the agent sets `agent_status.capability_drift`. This does not change detection outcome; it allows the server or dashboard to alert on silent detection degradation.
