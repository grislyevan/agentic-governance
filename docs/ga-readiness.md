# GA Readiness: Detec v1.0

**Prepared for:** Security reviewer / buyer due diligence
**Date:** 2026-03-24
**Version:** 0.4.0 (targeting v1.0 GA)

This document is a standalone GA-readiness summary. All claims reference canonical source documents; reviewers should consult those files for full detail.

---

## 1. Functional Checklist

| Feature | Status | Notes | Reference |
|---------|--------|-------|-----------|
| Behavioral detection (4 core signatures + evasion) | Available | DETEC-BEH-CORE-01–04; evasion validated LAB-RUN-EVASION-001 | [docs/product-status.md](product-status.md) |
| Approval workflow (create / approve / deny) | Available (backend); UI Roadmap | API endpoints shipped; hold label logged; enforcement gating not yet wired | [docs/product-status.md](product-status.md), [docs/enforcement-remaining-work.md](enforcement-remaining-work.md) |
| Allow-list governance (tenant-scoped, expiring) | Available (backend); UI Roadmap | Full CRUD API shipped with audit trail; dashboard UI is Roadmap | [docs/product-status.md](product-status.md) |
| Policy simulation | Available | Per-session policy simulation in session reports | [docs/product-status.md](product-status.md) |
| Telemetry / observability | Available | Prometheus metrics, EventStore diagnostics, capability drift detection | [docs/telemetry-and-performance.md](telemetry-and-performance.md) |
| Audit log | Available | Immutable, tenant-scoped, fail-open with metric; no delete endpoint | [docs/hardening-checklist.md](hardening-checklist.md) |
| Multi-tenant isolation | Available | Enforced at API + DB query layer on all resource paths | [docs/security-evidence-pack.md](security-evidence-pack.md) |

---

## 2. Security Controls Summary

Full detail: [docs/security-evidence-pack.md](security-evidence-pack.md)

| Area | Control | Verification | Status |
|------|---------|--------------|--------|
| Threat model | STRIDE analysis across API, Gateway, Collector, Dashboard; key trust boundaries documented | docs/threat-model.md | Applied |
| Security headers | X-Content-Type-Options, X-Frame-Options, HSTS (prod/staging), CSP, Referrer-Policy, Permissions-Policy — including on error paths | Unit tests (test_security_pentest.py) + manual curl on deploy | Applied |
| Error handling | Global exception handler returns generic message only; no stack traces or internal detail in production | Unit tests | Applied |
| Authentication | JWT HS256 pinned (alg=none rejected); API key prefix+hash; refresh token reuse rejected; agent key separate from user key | Unit tests (TestAPI2BrokenAuth) | Applied |
| Tenant isolation (BOLA) | All resource access scoped by tenant_id from auth context; mutation paths use strict_tenant_filter | Pentest tests (TestAPI1) | Applied |
| Rate limiting | Per-route, per-IP limits via SlowAPI: login 5/min, register 3/min, events 120/min, enforcement 30/min | Unit tests (test_rate_limits.py) | Applied |
| CI security gates | Semgrep SAST, Trivy dependency scan, pip-audit + npm audit, Gitleaks secrets detection, API pentest suite — all block merge on failure | .github/workflows/security.yml | Active on every PR to main |

---

## 3. Scale Envelope & Known Bottlenecks

Full detail: [docs/large-fleet-scenario.md](large-fleet-scenario.md)

### Scale envelope

| Component | Tested / Supported Scale | Notes |
|-----------|--------------------------|-------|
| SQLite backend | <50 endpoints (evaluation only) | Concurrent writes cause lock contention; not for production |
| PostgreSQL backend | 100–500 endpoints (single server) | Recommended for all production deployments |
| TCP Gateway (port 8001) | 50 concurrent connections validated | OS file descriptor limits apply; no explicit cap in gateway code |
| HTTP event ingest | 120 events/min per source IP | SlowAPI rate limit; use TCP gateway for high-throughput burst ingest |
| Heartbeat ingest | 60 heartbeats/min per source IP | Per-IP bucket; per-endpoint API keys recommended for large fleets |

### Bottleneck matrix

| Component | Known bottleneck | Condition | Mitigation |
|-----------|-----------------|-----------|------------|
| API rate limiter (SlowAPI, IP-keyed) | 60 heartbeats/min, 120 events/min | All agents share one source IP (NAT or simulation) | Per-endpoint API keys with multi-IP client distribution |
| SQLite | Not suitable for concurrent writes | >10 concurrent agents writing simultaneously | Use PostgreSQL in all production deployments |
| Gateway SessionRegistry | Linear scan for broadcast; acceptable <100 sessions | Large fleet broadcast storms | Review for deployments >500 endpoints |
| EventStore ring buffer | 10,000 events/agent max; at ~2 Hz scan rate fills in ~80 min | High-frequency scan with slow API ingest | Tune retention_seconds and max_events |

---

## 4. Known Limitations

Full detail: [docs/known-limitations.md](known-limitations.md)

| Category | One-line summary |
|----------|-----------------|
| Telemetry constraints | Psutil polling (60s default interval) is the production path; real-time syscall telemetry (ESF/ETW/eBPF) is not yet baseline-active |
| Confidence caveats | High-risk tools (e.g. Claude Code) commonly report Medium confidence without EDR enrichment; scores are point-in-time against calibration fixtures |
| Policy and enforcement | "Approval Required" labels are logged but do not block execution; ISO-001 container isolation is advisory only; Linux network block affects full UID not just target process |
| Deployment | Multi-tenant isolation is logical (DB query layer), not physical; >500 endpoint deployments not formally load-tested |
| Detection scope | Detec is not a general-purpose EDR; it does not monitor browser activity, inspect LLM prompts, or detect non-AI software categories |

---

## 5. Test Coverage Snapshot

Source: [PROGRESS.md](../PROGRESS.md) — snapshot as of 2026-03-21

| Suite | Tests |
|-------|-------|
| Collector | 849 |
| API | 421 |
| Protocol | 48 |
| **Total** | **1,318** |

**Lab validation runs:** 16 completed lab runs across 10 tools (8 live, 4 protocol-expected, 1 live/evasion). See [PROGRESS.md](../PROGRESS.md) for the full run table.

**CI gates:** Calibration regression gate is active — any change to confidence scoring logic requires updated fixture evidence before merging. Security test suite (pentest, gateway, rate limits) gates every PR to main.

---

## 6. Deployment Prerequisites

Full detail: [docs/pilot-runbook.md](pilot-runbook.md)

Before go-live the following must be in place:

- Detec server is running and accessible from endpoint machines (HTTP/HTTPS port 8000; TCP gateway port 8001 if used).
- An API key with `admin` or `owner` role is provisioned.
- Endpoint machines have Python 3.11+ installed.
- **macOS:** Full Disk Access granted to the Python process or installed agent binary.
- **Windows:** Scheduled task template deployed; user account with process-list access. Note: Windows agent runs as a user-account scheduled task, not a system service — this limits enforcement posture.
- **Linux:** systemd service template deployed; `psutil` readable without elevated permissions for target user.
- Recommended: PostgreSQL backend for deployments with more than ~10 concurrent endpoints.
- Recommended: Start in `enforcement_enabled: false` (visibility-only) mode; tune policy before escalating to enforcement.

The pilot follows a staged rollout: 5 endpoints → 10 endpoints → 25 endpoints, with go/no-go gates defined in [docs/pilot-go-no-go-checklist.md](pilot-go-no-go-checklist.md).

---

## 7. Open Items Before GA

The following items are tracked as blocking or near-blocking for a v1.0 GA declaration:

- **Approval Required enforcement wiring** — "Approval Required" decisions surface a hold label and create an approval record but do not currently block agent execution pending human review. Blocking execution is a Roadmap item. Operators must act manually on approval queue during this period. Tracked in [docs/enforcement-remaining-work.md](enforcement-remaining-work.md).
- **Live soak run** — The formal 24h/72h soak test defined in [docs/soak-test-runbook.md](soak-test-runbook.md) has not been executed against a dedicated staging environment. The most recent attempt (2026-03-24) failed to start due to a `PydanticUndefinedAnnotation` error in `api/routers/agent_download.py` in the local Python 3.11.6 environment. This is a local environment dependency issue; a clean staging run is needed before GA.
- **Lighthouse performance baseline** — No Lighthouse/Web Vitals baseline has been captured for the dashboard. Requires a served build environment. Non-blocking for security reviewers; required for performance SLA commitments.
- **G3 tenant / admin dashboard UX** — Tenant switcher, approval flow UI, and allow-list management UI are listed as Roadmap in [docs/product-status.md](product-status.md). The backend APIs are complete and tested; the frontend workflow is deferred to a separate sprint.
- **Agent key rotation** — Tracked as deferred post-sprint/remediation-1. API key rotation for user keys is available; per-agent key rotation lifecycle is not yet implemented.

---

*For any section, consult the referenced canonical docs. This document does not duplicate content from those sources.*
