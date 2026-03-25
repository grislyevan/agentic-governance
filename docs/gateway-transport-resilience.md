# Gateway and Transport Resilience

This document describes the transport modes available to the collector agent, the failover and recovery behavior, the data-loss profile for each mode, known limitations, recommended configuration, and available observability signals.

All behavior described here is derived from the implementation in `collector/output/adaptive_emitter.py`, `collector/output/tcp_emitter.py`, and `collector/output/http_emitter.py`.

---

## Transport Modes

### HTTP Mode

- **Endpoints used:** `POST /api/events`, `POST /api/endpoints/heartbeat`
- **Connection model:** Stateless; each request is an independent HTTP call with per-request API key authentication via `X-API-Key` header.
- **Auth:** Validated on every request.
- **When active:** Used when the collector is configured with `protocol: http`, or when the adaptive emitter has fallen back from TCP.

### TCP Mode

- **Endpoint:** TCP port 8001 (binary wire protocol; see `docs/wire-protocol.md`)
- **Connection model:** Persistent TCP connection (optionally TLS-wrapped). Authentication is performed once per session at connect time via an `AUTH` message; subsequent `EVENT`, `EVENT_BATCH`, and `HEARTBEAT` messages use the established session.
- **When active:** Used when `protocol: tcp` is configured, or when the adaptive emitter successfully probes TCP at startup.
- **Background behavior:** A background thread runs an asyncio event loop that manages the connection. Events are batched (up to 50 per batch, 1-second window) before sending. A reconnection loop with exponential backoff (`1s` base, `60s` max) retries on connection loss.

### Adaptive Mode (`protocol: auto`)

- **Startup behavior:** On startup, `AdaptiveEmitter` calls `try_tcp_auth()` — a synchronous probe that opens a TCP connection, sends an `AUTH` message, and waits for `AUTH_OK`. If the probe succeeds, a `TcpEmitter` is created and TCP is used for all subsequent sends. If the probe fails (connection refused, auth rejected, or timeout), the emitter switches immediately to HTTP fallback.
- **Failover trigger:** Once operating in TCP mode, the `TcpEmitter` tracks consecutive connect/auth failures. If `connect_fail_streak >= failover_threshold` **and** the disconnect has lasted at least 1 second, the failover callback fires (`on_degraded`). The `AdaptiveEmitter` sets `_prefer_http = True` and clears the TCP emitter reference.
- **Recovery:** A background `transport-recovery` thread polls `try_tcp_auth()` at `tcp_retry_interval` (default 30 seconds). When two consecutive probes succeed (separated by `tcp_recovery_stability` seconds; default 10 seconds), a new `TcpEmitter` is spawned, `_prefer_http` is set back to `False`, and buffered events are flushed via `flush_buffer()`.

---

## Failover Behavior

The failover path is triggered inside `TcpEmitter._connection_manager()` whenever `_should_failover()` returns `True`. The logic is:

```
failover_threshold is not None
AND on_degraded is not None
AND disconnect_since is not None
AND connect_fail_streak >= failover_threshold
AND (time.monotonic() - disconnect_since) >= 1.0
```

Key parameters (set by `AdaptiveEmitter` when spawning a `TcpEmitter`):

| Parameter | Default | Description |
|---|---|---|
| `failover_threshold` | 5 | Consecutive failures required to trigger failover |
| `tcp_retry_interval` | 30s | How often the recovery thread probes TCP |
| `tcp_recovery_stability` | 10s | Gap between two successful probes before TCP is restored |
| `tcp_connect_timeout` | 3s | Probe and connect timeout |

When failover fires, `_execute_failover()` runs: it calls `on_before_failover` (sets `_prefer_http = True`), spills the send queue to the local buffer, then calls `on_degraded` (which clears `_tcp = None` and logs the switch). The background TCP loop then exits.

Recovery back to TCP is handled entirely by the `AdaptiveEmitter._recovery_worker` thread, not by `TcpEmitter` itself.

---

## Data Loss Profile

### HTTP Mode

Each `POST /api/events` request is independent. If a request fails, the caller (the collector agent's send loop) receives the failure synchronously. No events are silently lost by the transport; the caller is responsible for retry. The heartbeat interval (default 60 seconds) provides natural retry pacing.

### TCP Mode

TCP is connection-based. Events are placed on an in-process queue (max 5,000 items) and sent by a background thread. If the connection drops mid-flight:

- Events that have been dequeued but not yet acknowledged (in the `_process_queue` batch loop) are not automatically re-queued. They may be lost on connection drop.
- Events still on the send queue are preserved in memory and will be re-sent when the connection is re-established (reconnect loop).
- If the TCP connection remains down for more than `_BUFFER_FALLBACK_THRESHOLD` seconds (300 seconds / 5 minutes), `_spill_queue_to_buffer()` moves queued events to the `LocalBuffer` on disk. These can be recovered when connectivity resumes.

### Adaptive Mode (TCP→HTTP Failover)

- Events emitted **after** `_prefer_http` is set are routed to `HttpEmitter` with no additional loss.
- Events already in the TCP `send_queue` at the moment failover fires are spilled to `LocalBuffer` by `_execute_failover()` and are not lost.
- Events that were in-flight (dequeued from the send queue, handed to `_process_queue`, but not yet ACKed by the server) at the exact moment the connection drops may be lost. This is the same window as plain TCP mode.
- After recovery (TCP restored), `AdaptiveEmitter.flush_buffer()` is called to re-queue buffered events over TCP.

---

## Known Limitations and Gaps

1. **TCP ACK loss on mid-flight drop.** Events that have been dequeued from the send queue and placed into a batch in `_process_queue` but not yet transmitted (or transmitted but not ACKed) when the connection is lost are not recovered. There is no message-level sequence tracking for retry on the client side.

2. **Recovery thread is always running.** Even when `protocol: tcp` is configured without `AdaptiveEmitter`, there is no recovery thread — that is fine. But in adaptive mode the recovery thread starts unconditionally at construction and runs for the lifetime of the process. This is intentional but means a daemon thread is always present.

3. **`try_tcp_auth` is blocking.** The startup probe and recovery probe both call `asyncio.run()` synchronously. On slow or firewalled networks this blocks the caller for up to `tcp_connect_timeout` seconds. The default is 3 seconds; set `tcp_connect_timeout` to a lower value for faster startup in environments with no gateway.

4. **No heartbeat during transport downgrade window.** Between the TCP failover trigger and the first successful HTTP heartbeat, there is a gap. The HTTP emitter does not automatically send a heartbeat on fallback; the next scheduled heartbeat call from the agent loop will use HTTP.

5. **Local buffer is per-process and in-memory or on-disk depending on `LocalBuffer` configuration.** On process crash during the downgrade window, buffered events that have not yet been flushed to disk are lost.

---

## Recommended Configuration for Resilience

**For pilot deployments (small fleet, intermittent connectivity):**

```json
{
  "protocol": "auto",
  "tcp_failure_threshold": 3,
  "tcp_retry_interval": 30,
  "tcp_recovery_stability": 10
}
```

This gives quick failover (3 consecutive failures) while avoiding flapping on transient drops.

**For high-reliability production deployments:**

Use TCP gateway with external monitoring on `detec_gateway_transport_errors_total`. Set `failover_threshold` high enough to tolerate brief network hiccups (e.g. 5–10) and ensure PostgreSQL is used as the backend. Monitor `detec_active_connections` for unexpected drops.

**For intermittent or high-latency networks:**

Use `protocol: http` directly — the stateless HTTP path is simpler and every request is independently retried by the caller. There is no session state to lose. The heartbeat interval provides the reconnect mechanism implicitly.

---

## Observability

The following Prometheus metrics are available at `GET /metrics` (from `api/core/metrics.py`) and are relevant to transport health:

| Metric | Type | Description |
|---|---|---|
| `detec_active_connections` | Gauge | Number of active TCP gateway connections. Drop to zero indicates all agents have disconnected or gateway is unreachable. |
| `detec_gateway_transport_errors_total` | Counter | Transport/session errors (connection lost, session crash). Sustained growth indicates connectivity problems. |
| `detec_gateway_decode_errors_total` | Counter | Frame decode errors (malformed or oversized frames). Non-zero values indicate protocol mismatch or corrupted data. |
| `detec_gateway_handler_errors_total` | Counter | Per-message handler errors. Session continues; indicates application-level processing failures. |
| `detec_gateway_db_errors_total` | Counter | Database errors during gateway auth, ingest, or heartbeat processing. |
| `detec_events_ingested_total` | Counter | Total events ingested via HTTP or TCP. Use this to confirm events are reaching the server after a failover event. |
| `http_requests_total` | Counter | Total HTTP requests by method, path, and status. Use `path="/api/events"` and `status="429"` to detect rate-limit pressure. |

Alert recommendations:

- Alert if `detec_gateway_transport_errors_total` increases by more than 10 in a 5-minute window.
- Alert if `detec_active_connections` drops to 0 during expected operating hours.
- Alert if `detec_events_ingested_total` stops increasing while endpoints are known to be active.
