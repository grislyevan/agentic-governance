# Forward Priorities: Development Task Breakdown

**Generated:** 2026-03-12
**Source:** `forward_priorities_a_b_c.plan.md`
**Codebase state:** M4 boundary, 233 collector tests, 122 API tests, 45 protocol tests passing. CI/CD, deploy configs, observability, security, retention all complete.

---

## How to Use This Document

Each task is scoped to roughly 30-60 minutes of focused implementation. Tasks are grouped by priority (A/B/C) and sub-feature. Dependencies are called out explicitly. Acceptance criteria tell you when a task is done.

**Status key:** `[ ]` not started, `[~]` in progress, `[x]` done, `[-]` cancelled

---

## Priority A: Demo and Sales Readiness

**Goal:** Make the product impressive without a live agent running.
**Total effort:** 5-8 days across 3 workstreams.
**Unlocks:** Sales conversations, investor demos, first cloud validation.

### A1. Demo Mode (INIT-37)

> Reference: `init-issues/INIT-37-demo-script-evidence-pack.md`
> Today: `_seed()` in `api/main.py:213-290` seeds admin + tenant + 15 baseline policies. No events, no endpoints, no enforcement data.

#### A1.1 Config flag and settings

**Description:** Add `DEMO_MODE` env flag and supporting config to the API settings.

**Files:**
- `api/core/config.py` (edit: add `demo_mode: bool = False` near line 102)
- `api/.env.example` (edit: document `DEMO_MODE`)

**Acceptance criteria:**
- `DEMO_MODE=true` is readable via `settings.demo_mode`
- Default is `False`; no behavior change when unset
- `.env.example` documents the flag

**Dependencies:** None
**Effort:** 15 min

---

#### A1.2 Demo seed module: endpoints and tools

**Description:** Create `api/core/demo_seed.py` with a function that generates 3 realistic endpoints (macOS, Windows, Linux) and registers them in the DB.

**Files:**
- `api/core/demo_seed.py` (new)

**Data to seed:**
- macOS endpoint: hostname `demo-mbp-eng01`, platform `darwin`, arch `arm64`
- Windows endpoint: hostname `demo-ws-fin02`, platform `win32`, arch `x86_64`
- Linux endpoint: hostname `demo-srv-devops03`, platform `linux`, arch `x86_64`

**Acceptance criteria:**
- `seed_demo_endpoints(db, tenant_id)` creates 3 `Endpoint` rows
- Function is idempotent (re-run doesn't duplicate)
- Endpoints have realistic hostnames, OS info, agent version

**Dependencies:** A1.1
**Effort:** 30 min

---

#### A1.3 Demo seed module: events across 5 tool types

**Description:** Generate ~50 canonical events spanning 5 tools (Claude Code, Cursor, Ollama, Aider, OpenClaw) distributed across the 3 demo endpoints. Events should cover all major `event_type` values from the schema.

**Files:**
- `api/core/demo_seed.py` (edit: add `seed_demo_events()`)
- Reference: `schemas/canonical-event-schema.json` for event types and structure
- Reference: `collector/tests/fixtures/lab_runs/*.json` for realistic signal values

**Event distribution:**
- ~15 `detection.observed` (mix of tool classes A/B/C/D)
- ~10 `policy.evaluated` (linked to baseline policies)
- ~8 `enforcement.applied` / `enforcement.simulated` (mix of allow/detect/block)
- ~5 `attribution.updated` (confidence updates)
- ~5 `heartbeat.received` (one per endpoint + extras)
- ~4 `posture.changed` events
- ~3 `enforcement.escalated` / `enforcement.rate_limited`

**Acceptance criteria:**
- `seed_demo_events(db, tenant_id, endpoints)` inserts ~50 `Event` rows
- Events span a 7-day window (backdated from seed time)
- `payload` JSON matches canonical schema structure
- Events reference valid `endpoint_id` and `rule_id` values
- Tool attribution scores vary realistically (0.55-0.95)

**Dependencies:** A1.2, baseline policies seeded
**Effort:** 60-90 min (most complex seed task)

---

#### A1.4 Demo seed module: policy evaluations with mixed decisions

**Description:** Ensure demo events include policy evaluation data that exercises the full decision spectrum: allow, detect, block, escalate.

**Files:**
- `api/core/demo_seed.py` (edit: extend event payloads)

**Decision distribution:**
- ~60% allow (routine tool use within policy)
- ~20% detect (flagged but not blocked)
- ~10% block (policy violation)
- ~10% escalate / require approval

**Acceptance criteria:**
- Events with `decision_state` field populated
- `rule_id` references real baseline policy IDs (ENFORCE-001 through ENFORCE-006, etc.)
- `severity_level` varies: info/low/medium/high/critical
- Dashboard EventsPage and PoliciesPage show meaningful data

**Dependencies:** A1.3
**Effort:** 30 min (mostly payload tuning)

---

#### A1.5 Demo seed module: enforcement events

**Description:** Create 2-3 enforcement action records that demonstrate the enforcement ladder (warn, throttle, block, kill).

**Files:**
- `api/core/demo_seed.py` (edit: add enforcement events)
- Reference: `api/models/enforcement.py` for enforcement record schema (if exists, otherwise embed in event payloads)

**Acceptance criteria:**
- At least 1 simulated enforcement (dry-run mode)
- At least 1 applied enforcement (block action)
- At least 1 escalated enforcement (approval required)
- Each links back to the triggering event and policy rule

**Dependencies:** A1.4
**Effort:** 30 min

---

#### A1.6 Wire demo seed into startup

**Description:** Call the demo seed functions from `_seed()` in `api/main.py` when `DEMO_MODE=true`.

**Files:**
- `api/main.py` (edit: extend `_seed()` around line 290)

**Logic:**
1. After normal seed (tenant + admin + policies), check `settings.demo_mode`
2. If true, call `seed_demo_endpoints()`, then `seed_demo_events()`
3. Log clearly: "Demo mode: seeded N endpoints and M events"

**Acceptance criteria:**
- `DEMO_MODE=true` startup seeds full demo dataset
- `DEMO_MODE=false` (default) behavior unchanged
- Idempotent: re-running startup doesn't duplicate demo data

**Dependencies:** A1.1 through A1.5
**Effort:** 20 min

---

#### A1.7 Demo reset endpoint

**Description:** Add `POST /api/demo/reset` (owner only) that wipes and re-seeds demo data.

**Files:**
- `api/routers/demo.py` (new)
- `api/main.py` (edit: register router)

**Behavior:**
1. Guard: return 403 if `demo_mode` is false
2. Guard: require owner role
3. Delete all events, endpoints (except the admin user and tenant)
4. Re-run demo seed functions
5. Return `{"status": "reset", "events": N, "endpoints": 3}`

**Acceptance criteria:**
- Only accessible when `DEMO_MODE=true`
- Only owner role can call it
- Demo data is fully refreshed
- Non-demo data (admin user, tenant, policies) preserved

**Dependencies:** A1.6
**Effort:** 30 min

---

#### A1.8 Demo status endpoint

**Description:** Add `GET /api/demo/status` that returns whether demo mode is active and data stats.

**Files:**
- `api/routers/demo.py` (edit)

**Response:**
```json
{
  "demo_mode": true,
  "endpoints": 3,
  "events": 50,
  "last_reset": "2026-03-12T10:00:00Z"
}
```

**Acceptance criteria:**
- Returns `demo_mode: false` and empty stats when not in demo mode
- Returns accurate counts when demo mode is active

**Dependencies:** A1.7
**Effort:** 15 min

---

#### A1.9 Dashboard demo banner

**Description:** Show a subtle "Demo Environment" banner when the API reports demo mode is active.

**Files:**
- `dashboard/src/components/layout/DemoBanner.jsx` (new)
- `dashboard/src/App.jsx` (edit: render banner above main content)
- `dashboard/src/lib/api.js` (edit: add `getDemoStatus()` call)

**Design:**
- Amber/yellow pill or strip below TopBar
- Text: "Demo Environment - Showing sample data"
- Dismiss button (session only, reappears on reload)

**Acceptance criteria:**
- Banner visible on all pages when demo mode active
- Not visible when demo mode is off
- Doesn't interfere with dashboard layout or scrolling
- Accessible (contrast ratio, screen reader label)

**Dependencies:** A1.8
**Effort:** 30 min

---

#### A1.10 Demo mode tests

**Description:** Add tests for the demo seed and reset flow.

**Files:**
- `api/tests/test_demo.py` (new)

**Tests:**
1. Demo seed creates expected number of endpoints and events
2. Demo reset wipes and re-creates data
3. Demo endpoints return 403 when `DEMO_MODE=false`
4. Demo reset requires owner role
5. Demo data is schema-valid (events match canonical schema)

**Acceptance criteria:**
- All tests pass
- Covers happy path and auth/guard edge cases

**Dependencies:** A1.7, A1.8
**Effort:** 45 min

---

### A2. Capability Brief (INIT-32/INIT-33)

> Reference: `init-issues/INIT-33-one-page-capability-brief.md`, `branding/one-sheet.md`, `branding/brand-foundation.md`
> Today: Brand content exists. No assembled brief. LaTeX template at `compliance/templates/default.latex`.

#### A2.1 Draft capability brief content

**Description:** Assemble the one-page capability brief in Markdown following INIT-33 structure: Headline, What We Detect, How We Decide, What We Enforce, Proof and Validation, Known Limits, CTA.

**Files:**
- `branding/capability-brief.md` (new)

**Content sources:**
- `branding/one-sheet.md`: Problem statement, tool classes, detection model
- `branding/brand-foundation.md`: Positioning, audience, tagline
- `lab-runs/`: Specific lab results for claim validation
- `playbook/PLAYBOOK-v0.4-*.md`: Detection profiles, confidence bands

**Rules (from INIT-33):**
- Every claim must be measured, validated, or labeled roadmap
- No "100% detection" or unstated assumptions
- Specific lab run numbers for proof

**Acceptance criteria:**
- Follows INIT-33 structure exactly
- All claims backed by specific evidence (lab run IDs, test counts)
- Under 1 page when rendered (targeting ~500 words)

**Dependencies:** None (writing task, not code)
**Effort:** 2-3 hours

---

#### A2.2 PDF export pipeline

**Description:** Create a Markdown-to-PDF pipeline for the capability brief using pandoc + a customized LaTeX template (adapt from `compliance/templates/default.latex`).

**Files:**
- `branding/templates/brief.latex` (new, adapted from compliance template)
- `branding/Makefile` or `branding/build-brief.sh` (new)

**Pipeline:**
```bash
pandoc capability-brief.md -o capability-brief.pdf --template=templates/brief.latex
```

**Acceptance criteria:**
- `make brief` or `./build-brief.sh` produces `capability-brief.pdf`
- PDF uses Detec branding (colors, logo if available)
- Renders cleanly as a single page

**Dependencies:** A2.1, pandoc installed
**Effort:** 1-2 hours

---

### A3. Live Deploy Test

> Reference: `.github/workflows/release.yml`, `fly.toml`, `SERVER.md`
> Today: Release workflow has 5 jobs. `fly.toml` targets `detec-api` on port 8000. TCP gateway (8001) not exposed.

#### A3.1 Tag and release v0.1.0

**Description:** Create and push the `v0.1.0` tag. Verify all 5 release workflow jobs complete successfully.

**Steps:**
1. Ensure `main` is clean and CI passes
2. `git tag v0.1.0 && git push origin v0.1.0`
3. Monitor GitHub Actions release workflow
4. Verify artifacts: dashboard build, Docker images on GHCR, macOS .pkg, Windows .zip, GitHub Release page

**Acceptance criteria:**
- All 5 release jobs green
- GitHub Release page has macOS and Windows artifacts
- Docker images tagged `v0.1.0` on GHCR

**Dependencies:** All A1 tasks (demo mode should be in the release)
**Effort:** 1 hour (mostly waiting + debugging)

---

#### A3.2 Deploy to Fly.io

**Description:** Deploy the API to Fly.io with Fly Postgres. Configure secrets and verify health.

**Steps:**
1. `fly launch` (or `fly deploy` if app exists)
2. `fly postgres create` and attach
3. Set secrets: `JWT_SECRET`, `SEED_ADMIN_PASSWORD`, `ALLOWED_ORIGINS`, `DEMO_MODE=true`
4. Verify `/api/health` returns healthy
5. Verify dashboard loads at root

**Acceptance criteria:**
- `https://detec-api.fly.dev/api/health` returns `{"status": "healthy"}`
- Dashboard loads and shows demo data
- Admin can log in with seeded credentials

**Dependencies:** A3.1
**Effort:** 1-2 hours

---

#### A3.3 End-to-end agent connection test

**Description:** Connect a local collector agent to the Fly.io-deployed server. Verify events flow.

**Steps:**
1. `detec-agent --api-url https://detec-api.fly.dev --api-key <key> --dry-run --verbose`
2. Verify events appear in deployed dashboard
3. Test heartbeat endpoint

**Acceptance criteria:**
- Agent connects successfully
- At least one event visible in deployed dashboard
- Heartbeat shows endpoint as "online"

**Dependencies:** A3.2
**Effort:** 30 min

---

#### A3.4 Document deploy session

**Description:** Write up findings, issues, and fixes from the deploy.

**Files:**
- `docs/session-first-cloud-deploy.md` (new)

**Acceptance criteria:**
- Documents what worked, what broke, and what was fixed
- Includes exact commands used
- Notes any config or workflow changes needed

**Dependencies:** A3.3
**Effort:** 30 min

---

## Priority B: Revenue Gate

**Goal:** Paying customers can subscribe and the system handles production credentials safely.
**Total effort:** 10-15 days across 3 workstreams.
**Unlocks:** Revenue, production customer onboarding.

### B1. Stripe Billing

> Done. Tenant model has billing columns (stripe_customer_id, subscription_tier, subscription_status, trial_ends_at, stripe_subscription_id). Stripe SDK integrated. Tier limits enforced. Billing dashboard and 23 tests complete.

#### B1.1 Tenant model: add billing columns

**Description:** Add billing fields to the Tenant model.

**Files:**
- `api/models/tenant.py` (edit)

**New columns:**
- `stripe_customer_id: str | None` (String 64, nullable)
- `subscription_tier: str` (String 16, default `"free"`)
- `subscription_status: str` (String 24, default `"active"`)
- `trial_ends_at: datetime | None` (DateTime, nullable)

**Acceptance criteria:**
- Model compiles without errors
- Default tier is "free", default status is "active"
- Existing tenants unaffected (nullable / has defaults)

**Dependencies:** None
**Effort:** 15 min

---

#### B1.2 Alembic migration 0012: billing columns

**Description:** Create migration to add billing columns to tenants table.

**Files:**
- `api/alembic/versions/0012_add_billing_columns.py` (new)

**Acceptance criteria:**
- `alembic upgrade head` adds columns
- `alembic downgrade -1` removes them
- Existing data preserved (columns nullable or have defaults)

**Dependencies:** B1.1
**Effort:** 20 min

---

#### B1.3 Stripe SDK and config

**Description:** Add `stripe` to API dependencies and billing config settings.

**Files:**
- `api/requirements.txt` (edit: add `stripe`)
- `api/core/config.py` (edit: add Stripe settings)
- `api/.env.example` (edit: document Stripe env vars)

**New settings:**
- `stripe_secret_key: str = ""`
- `stripe_webhook_secret: str = ""`
- `stripe_price_pro: str = ""`
- `stripe_price_enterprise: str = ""`

**Property:**
- `stripe_configured -> bool`: True when `stripe_secret_key` is set

**Acceptance criteria:**
- `pip install -r requirements.txt` installs stripe
- Settings load from env vars
- No crash when Stripe keys are empty

**Dependencies:** None
**Effort:** 15 min

---

#### B1.4 Billing core module

**Description:** Create `api/core/billing.py` with Stripe client wrapper and business logic.

**Files:**
- `api/core/billing.py` (new)

**Functions:**
- `create_checkout_session(tenant, price_id)` -> Stripe checkout session URL
- `create_customer_portal_session(tenant)` -> Stripe portal URL
- `handle_subscription_updated(event)` -> update tenant tier/status
- `handle_invoice_paid(event)` -> confirm active subscription
- `handle_subscription_deleted(event)` -> downgrade to free

**Acceptance criteria:**
- All functions handle Stripe API errors gracefully
- Tenant tier mapping: `price_pro` -> "pro", `price_enterprise` -> "enterprise"
- Functions are unit-testable with mocked Stripe client

**Dependencies:** B1.1, B1.3
**Effort:** 60-90 min

---

#### B1.5 Billing router

**Description:** Create billing API endpoints.

**Files:**
- `api/routers/billing.py` (new)
- `api/main.py` (edit: register router)

**Endpoints:**
- `POST /api/billing/checkout` - Create checkout session (owner only)
- `GET /api/billing/portal` - Redirect to Stripe portal (owner only)
- `POST /api/billing/webhook` - Stripe webhook receiver (no auth, verify signature)
- `GET /api/billing/status` - Current subscription state (any authenticated user)

**Acceptance criteria:**
- Checkout creates a Stripe session and returns URL
- Portal redirects to Stripe customer portal
- Webhook verifies Stripe signature before processing
- Status returns tier, status, trial_ends_at
- All billing endpoints return 503 when Stripe is not configured

**Dependencies:** B1.4
**Effort:** 60 min

---

#### B1.6 Tier enforcement middleware

**Description:** Add middleware that checks subscription tier limits on API requests.

**Files:**
- `api/core/tier_limits.py` (new)
- `api/main.py` or relevant routers (edit: apply tier checks)

**Tier limits:**
| Tier | Endpoints | Events/month | Features |
|------|-----------|-------------|----------|
| free | 3 | 1,000 | Core detection |
| pro | 25 | Unlimited | + enforcement, webhooks |
| enterprise | Unlimited | Unlimited | + SSO, SIEM, priority support |

**Acceptance criteria:**
- Free tier: 4th endpoint registration returns 402 with upgrade message
- Free tier: event ingestion returns 402 after 1,000 events in current month
- Pro/enterprise: no endpoint or event limits
- Tier check is a reusable dependency, not duplicated per router

**Dependencies:** B1.2 (needs billing columns in DB)
**Effort:** 60 min

---

#### B1.7 Dashboard billing page

**Description:** Add a billing page to the dashboard.

**Files:**
- `dashboard/src/pages/BillingPage.jsx` (new)
- `dashboard/src/components/layout/Sidebar.jsx` (edit: add nav item)
- `dashboard/src/App.jsx` (edit: add route)
- `dashboard/src/lib/api.js` (edit: add billing API calls)

**UI elements:**
- Current plan badge (free/pro/enterprise)
- Usage summary: endpoints used / limit, events this month / limit
- Upgrade button (opens Stripe checkout)
- Manage subscription button (opens Stripe portal)
- Trial countdown (if applicable)

**Acceptance criteria:**
- Billing page accessible from sidebar
- Shows current plan and usage
- Upgrade button creates checkout session and redirects to Stripe
- Manage button redirects to Stripe portal
- Graceful state when Stripe is not configured ("Billing not available")

**Dependencies:** B1.5
**Effort:** 90 min

---

#### B1.8 Plan badge in settings/header

**Description:** Show the current plan tier as a badge in the settings page and optionally the sidebar.

**Files:**
- `dashboard/src/pages/SettingsPage.jsx` (edit)
- `dashboard/src/components/layout/Sidebar.jsx` (edit: optional badge)

**Acceptance criteria:**
- Settings page shows current plan
- Free plan shows subtle upgrade prompt

**Dependencies:** B1.7
**Effort:** 20 min

---

#### B1.9 Billing tests

**Description:** Write tests for billing endpoints and tier enforcement.

**Files:**
- `api/tests/test_billing.py` (new)

**Tests:**
1. Checkout session creation (mocked Stripe)
2. Webhook processing for subscription events (mocked)
3. Tier limit enforcement: free tier blocks at endpoint/event limits
4. Pro tier allows beyond free limits
5. Billing endpoints return 503 when Stripe not configured
6. Only owner can access checkout/portal

**Acceptance criteria:**
- All tests pass with mocked Stripe client
- Tier enforcement tested at boundary conditions

**Dependencies:** B1.5, B1.6
**Effort:** 60 min

---

### B2. Secrets Management

> Today: All credentials are env vars. `.env.example` documents them. Production validator rejects unsafe defaults. `docs/edr-credential-security.md` mentions Vault.

#### B2.1 Evaluate and document secrets approach

**Description:** Evaluate Fly.io secrets (if deploying on Fly), Doppler, and AWS Secrets Manager. Document the decision.

**Files:**
- `docs/secrets-management.md` (new)

**Evaluation criteria:**
- Cost (Fly secrets are free; Doppler free tier; AWS per-secret pricing)
- Complexity (Fly is simplest; Doppler medium; AWS most complex)
- Rotation support
- CI/CD integration
- Team size fit (solo/small team vs. enterprise)

**Recommendation:** Start with Fly.io secrets for the deploy target. Document migration path to Doppler/AWS if needed later.

**Acceptance criteria:**
- Decision documented with rationale
- Migration path noted for future scale
- List of secrets to manage: `JWT_SECRET`, `SEED_ADMIN_PASSWORD`, `DATABASE_URL`, Stripe keys

**Dependencies:** A3.2 (Fly deploy informs the decision)
**Effort:** 1-2 hours

---

#### B2.2 Implement chosen approach

**Description:** Configure the chosen secrets provider and migrate production credentials.

**Scope depends on B2.1 decision.** If Fly.io secrets:
- `fly secrets set JWT_SECRET=... SEED_ADMIN_PASSWORD=...` etc.
- Document exact commands in `SERVER.md`
- Update `fly.toml` if needed

If Doppler:
- `doppler.yaml` config
- CI integration in `.github/workflows/`
- `api/core/secrets.py` (new) with lazy loading

**Acceptance criteria:**
- No secrets in code, env files, or CI config
- Production deployment uses the chosen provider
- `SERVER.md` updated with secrets setup instructions

**Dependencies:** B2.1
**Effort:** 2-4 hours (depends on choice)

---

### B3. Uptime Monitoring

> Today: `/api/health` returns component-level status. `/metrics` exposes Prometheus metrics. `fly.toml` has internal health checks.

#### B3.1 Configure external uptime monitor

**Description:** Set up an external service to poll `/api/health` every 60s.

**Options:** UptimeRobot (free, 50 monitors), Better Uptime (free, 10 monitors), Checkly (free, 5 checks)

**Steps:**
1. Create account on chosen provider
2. Add HTTP check: `GET https://detec-api.fly.dev/api/health`
3. Set alert thresholds: degraded = warning, unhealthy = critical
4. Configure alert channels (email minimum, Slack if available)

**Acceptance criteria:**
- Monitor pings health endpoint every 60s
- Alert fires within 2 minutes of downtime
- At least one alert channel configured

**Dependencies:** A3.2 (need deployed instance)
**Effort:** 30 min

---

#### B3.2 Optional: Grafana Cloud for metrics

**Description:** Set up Grafana Cloud free tier to scrape Prometheus metrics from `/metrics`.

**Steps:**
1. Create Grafana Cloud free account
2. Configure Prometheus remote write or scrape target
3. Import or create basic dashboard: request rate, latency, error rate, event ingestion rate

**Acceptance criteria:**
- Metrics visible in Grafana
- Basic dashboard shows key operational metrics

**Dependencies:** A3.2
**Effort:** 1-2 hours

---

#### B3.3 Document monitoring setup

**Description:** Add monitoring configuration to `SERVER.md`.

**Files:**
- `SERVER.md` (edit: add monitoring section)

**Acceptance criteria:**
- Documents uptime monitor setup
- Documents Grafana setup (if done)
- Includes alert escalation guidance

**Dependencies:** B3.1
**Effort:** 20 min

---

## Priority C: Enterprise Procurement

**Goal:** Features SOC teams and procurement require before signing.
**Total effort:** 20-40 days across 4 workstreams.
**Unlocks:** Enterprise contracts, SOC team adoption.

### C1. SSO / OIDC

> Today: `auth_provider` column exists (default `"local"`). `password_reset_required` flag exists. No OIDC libraries, no SSO endpoints, no SSO UI.

#### C1.1 OIDC config and dependencies

**Files:**
- `api/requirements.txt` (edit: add `authlib`)
- `api/core/config.py` (edit: add OIDC settings)

**New settings:**
- `oidc_issuer: str = ""`
- `oidc_client_id: str = ""`
- `oidc_client_secret: str = ""`
- `oidc_redirect_uri: str = ""`

**Property:** `oidc_configured -> bool`

**Effort:** 15 min

---

#### C1.2 SSO auth routes

**Files:**
- `api/routers/auth.py` (edit: add SSO endpoints)

**Endpoints:**
- `GET /api/auth/sso/login` - Redirect to IdP authorization endpoint
- `GET /api/auth/sso/callback` - Exchange code, create/update user, issue JWT

**Effort:** 90 min

---

#### C1.3 SSO user provisioning

**Description:** When a user authenticates via SSO for the first time, create their user record with `auth_provider="oidc"`, no local password.

**Guard:** Users with `auth_provider != "local"` cannot use the password login endpoint.

**Effort:** 45 min

---

#### C1.4 Dashboard SSO UI

**Files:**
- `dashboard/src/pages/LoginPage.jsx` (edit: add "Sign in with SSO" button)
- `dashboard/src/pages/SettingsPage.jsx` (edit: tenant-level SSO config)

**Effort:** 60 min

---

#### C1.5 SSO tests

**Tests:** SSO login redirect, callback handling, user provisioning, password login blocked for SSO users.

**Effort:** 60 min

---

### C2. SIEM Connectors

> Today: Full webhook system with CRUD, HMAC, retries. Splunk HEC recipe in docs. No dedicated templates.

#### C2.1 Webhook template definitions

**Files:**
- `api/webhooks/templates.py` (new)

**Templates:** Splunk HEC, Elastic, Microsoft Sentinel (payload format, headers, URL pattern)

**Effort:** 60 min

---

#### C2.2 Template API endpoint

**Files:**
- `api/routers/webhooks.py` (edit: add `GET /api/webhooks/templates`)

**Effort:** 30 min

---

#### C2.3 Dashboard template selector

**Files:**
- `dashboard/src/pages/SettingsPage.jsx` (edit: template dropdown on webhook creation)

**Effort:** 45 min

---

#### C2.4 SIEM integration docs

**Files:**
- `docs/siem-integration.md` (new): Per-SIEM setup guide (Splunk, Elastic, Sentinel)

**Effort:** 2-3 hours

---

### C3. MITRE ATT&CK Mapping

> Today: 14 scanners, BEH-001 through BEH-008. INIT-40 in parking lot. No ATT&CK fields.

#### C3.1 ATT&CK mapping module

**Files:**
- `collector/engine/attack_mapping.py` (new)

**Mappings (initial set):**
| Signal | ATT&CK Technique |
|--------|-----------------|
| BEH-001 Shell fan-out | T1059 Command and Scripting Interpreter |
| BEH-002 LLM API cadence | T1071.001 Application Layer Protocol: Web |
| BEH-003 Multi-file burst | T1565.001 Data Manipulation: Stored Data |
| BEH-004 RMW loop | T1005 Data from Local System |
| BEH-005 Long session | T1078 Valid Accounts (persistence) |
| BEH-006 Credential access | T1552 Unsecured Credentials |
| BEH-007 Git automation | T1537 Transfer Data to Cloud Account |
| BEH-008 Process resurrection | T1543 Create or Modify System Process |
| Code generation (Class C/D) | T1204.002 User Execution: Malicious File |

**Effort:** 60 min

---

#### C3.2 Schema extension

**Files:**
- `schemas/canonical-event-schema.json` (edit: add `mitre_attack` object)

**New field:**
```json
"mitre_attack": {
  "technique_id": "T1059",
  "technique_name": "Command and Scripting Interpreter",
  "tactic": "Execution",
  "subtechnique": "T1059.004"
}
```

**Effort:** 30 min

---

#### C3.3 Event enrichment in collector

**Files:**
- `collector/main.py` (edit: populate ATT&CK fields during event construction)

**Effort:** 45 min

---

#### C3.4 Dashboard ATT&CK column

**Files:**
- `dashboard/src/pages/EventsPage.jsx` (edit: add column, filter)

**Effort:** 30 min

---

### C4. Compliance Reporting

> Today: SOC2 compliance program (61 controls). Audit log. Event retention. No export API.

#### C4.1 Report generation endpoint

**Files:**
- `api/routers/reports.py` (new)
- `api/core/report_generator.py` (new)

**Endpoint:** `POST /api/reports/compliance` with date range, format (PDF/CSV)

**Report content:** Endpoint inventory, event summary, policy coverage, enforcement actions, user access log

**Effort:** 90 min

---

#### C4.2 PDF generation

**Files:**
- `api/requirements.txt` (edit: add `weasyprint` or `reportlab`)
- `api/core/report_generator.py` (edit: PDF rendering)

**Effort:** 90 min

---

#### C4.3 Dashboard export button

**Files:**
- `dashboard/src/pages/AuditLogPage.jsx` (edit: add "Export Report" button, date range picker)

**Effort:** 45 min

---

## Dependency Graph

```
A1.1 ─→ A1.2 ─→ A1.3 ─→ A1.4 ─→ A1.5 ─→ A1.6 ─→ A1.7 ─→ A1.8 ─→ A1.9 ─→ A1.10
                                                                               ↓
A2.1 ─→ A2.2                                                              A3.1 ─→ A3.2 ─→ A3.3 ─→ A3.4
                                                                               ↓
                                                                        B2.1 ─→ B2.2
                                                                        B3.1 ─→ B3.2 ─→ B3.3

B1.1 ─→ B1.2 ─→ B1.4 ─→ B1.5 ─→ B1.6 ─→ B1.7 ─→ B1.8 ─→ B1.9
B1.3 ─────────↗

C1.1 ─→ C1.2 ─→ C1.3 ─→ C1.4 ─→ C1.5
C2.1 ─→ C2.2 ─→ C2.3 ─→ C2.4
C3.1 ─→ C3.2 ─→ C3.3 ─→ C3.4
C4.1 ─→ C4.2 ─→ C4.3
```

**Parallel lanes within Priority A:**
- A1 (demo mode) and A2 (capability brief) have zero dependencies on each other
- A3 (live deploy) depends on A1 being done (so demo data ships in v0.1.0)

**Parallel lanes within Priority B:**
- B1 (Stripe), B2 (secrets), B3 (uptime) are independent of each other
- B2 and B3 both depend on A3 (deployed instance)

**Priority C items** are all independent of each other and can run fully in parallel.

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Demo data looks fake / unconvincing | Medium | High | Use real lab-run signal values; vary timestamps naturally; get design review before demo |
| R2 | Stripe webhook signature verification fails in production | Medium | High | Test with Stripe CLI (`stripe listen --forward-to`); add comprehensive error logging |
| R3 | Fly.io deploy exposes config or secrets | Low | Critical | Use `fly secrets set`, never commit `.env`; validate ALLOWED_ORIGINS is set |
| R4 | Release workflow fails on first real tag | Medium | Medium | Do a dry run with a `v0.0.1-rc1` tag first |
| R5 | Free tier limits frustrate early adopters | Medium | Medium | Set limits generously initially; track usage before tightening |
| R6 | OIDC provider differences (Okta vs Azure AD vs Google) | High | Medium | Start with one provider (Okta); use authlib's generic OIDC support |
| R7 | PDF generation adds heavy dependencies (weasyprint needs system libs) | Medium | Low | Use reportlab (pure Python) or server-side HTML-to-PDF as fallback |

---

## Recommended Sprint Allocation

### Sprint 1 (Week 1): Demo Mode + Brief
- **Dev 1:** A1.1 through A1.6 (demo seed backend)
- **Dev 2:** A2.1 (capability brief writing)
- **End of sprint:** Demo mode works on local dev server

### Sprint 2 (Week 2): Demo Polish + Deploy
- **Dev 1:** A1.7 through A1.10 (demo router, banner, tests)
- **Dev 2:** A2.2 (PDF export) + A3.1 through A3.4 (live deploy)
- **End of sprint:** v0.1.0 tagged, deployed to Fly.io with demo data

### Sprint 3-4 (Weeks 3-4): Billing Foundation
- **Dev 1:** B1.1 through B1.5 (Stripe backend)
- **Dev 2:** B2.1, B2.2 (secrets), B3.1 through B3.3 (uptime)
- **End of sprint:** Stripe checkout works in test mode

### Sprint 5 (Week 5): Billing UI + Tier Enforcement
- **Dev 1:** B1.6 through B1.9 (tier limits, dashboard, tests)
- **End of sprint:** Full billing flow operational

### Sprint 6-8 (Weeks 6-10): Enterprise Features
- **Track 1:** C1 (SSO/OIDC) - 1.5 weeks
- **Track 2:** C2 (SIEM) + C3 (ATT&CK) in parallel - 1.5 weeks
- **Track 3:** C4 (Compliance Reporting) - 1 week
- These tracks can run in parallel with 2-3 developers
