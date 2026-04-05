# Wave 5 Track N — Reliability & Performance Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the soak harness blocker, execute a 24h soak run, establish a repeatable Lighthouse baseline with CI budget gates, and link capability-drift severity to an operator runbook.

**Architecture:** Three independent stories — (N1) diagnose and fix the `PydanticUndefinedAnnotation: name 'Platform' is not defined` crash in `api/routers/agent_download.py` then run the soak; (N2) create a serve-and-measure Lighthouse script with CI gate; (N3) wire the CapabilityDriftWidget's "view runbook" link to a new ops runbook doc.

**Tech Stack:** FastAPI + Pydantic v2 (API), Python pytest (API tests), scripts/soak/replay_traces.py (soak harness), Lighthouse CLI (perf baseline), GitHub Actions (CI), React (dashboard widget)

---

## File Map

### New files
- `docs/capability-drift-runbook.md` — Analyst response playbook for capability drift alerts
- `scripts/lighthouse/run.sh` — Headless Lighthouse measurement script
- `docs/dashboard-performance.md` — Updated with real LCP/FCP numbers (already exists; update)
- `.github/workflows/lighthouse.yml` — CI performance gate

### Modified files
- `api/routers/agent_download.py` — Fix PydanticUndefinedAnnotation
- `api/tests/test_agent_download.py` — Add regression test for the fixed crash
- `dashboard/src/components/dashboard/CapabilityDriftWidget.jsx` — Wire "view runbook" link to docs

---

## Task 1: N1 — Fix PydanticUndefinedAnnotation

**Files:**
- Modify: `api/routers/agent_download.py`
- Modify: `api/tests/test_agent_download.py`

### Background

`EnrollEmailRequest` in `agent_download.py` defines a field `platform: Platform` where `Platform` is an Enum defined in the same file. Under Pydantic v2, this annotation may fail during model rebuild (e.g., during FastAPI's OpenAPI schema generation or when the test suite imports the app) because Pydantic v2's annotation resolver uses `get_type_hints()` with a restricted namespace.

The root cause is that `Platform` is a local name that Pydantic v2 can't resolve if the model is rebuilt in a context where only the module's `__annotations__` dict is inspected without its full globals. The fix is to call `EnrollEmailRequest.model_rebuild()` after class definition with an explicit namespace, or to use a `TYPE_CHECKING` guard with a string annotation.

The simplest reliable fix for Pydantic v2: add `model_rebuild()` after class definition with `_types_namespace` pointing to the local names.

- [ ] **Step 1.1: Write a regression test that reproduces the error**

Add to `api/tests/test_agent_download.py`:

```python
def test_enroll_email_schema_rebuild_does_not_raise():
    """Regression: PydanticUndefinedAnnotation must not occur on schema rebuild."""
    from routers.agent_download import EnrollEmailRequest
    # Force Pydantic to rebuild the schema — this is what triggers the crash.
    EnrollEmailRequest.model_rebuild()
    # Also verify the schema is parseable (the field must accept Platform enum values).
    import json
    schema = EnrollEmailRequest.model_json_schema()
    assert "platform" in json.dumps(schema)
```

- [ ] **Step 1.2: Run the test to confirm it fails**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_agent_download.py::test_enroll_email_schema_rebuild_does_not_raise -v
```

Expected: `FAIL` with `PydanticUndefinedAnnotation: name 'Platform' is not defined` (or similar).

If it passes, the error may manifest differently — also try:
```bash
python -c "from routers.agent_download import EnrollEmailRequest; EnrollEmailRequest.model_rebuild()"
```

And check if the soak harness itself imports the full app:
```bash
cd /Users/echance/Documents/Cursor/agentic-governance
python -c "import api.main" 2>&1
```

Identify the exact line that raises; note it, then proceed to fix.

- [ ] **Step 1.3: Fix — add model_rebuild with explicit namespace**

In `api/routers/agent_download.py`, immediately after the `EnrollEmailRequest` class definition (after line ~408), add:

```python
# Pydantic v2: rebuild with explicit namespace so 'Platform' and 'Proto' resolve
# correctly even when the model is re-evaluated (e.g., during schema generation).
EnrollEmailRequest.model_rebuild(_types_namespace={"Platform": Platform, "Proto": Proto})
```

Also add the same after `EnrollEmailResponse` if it uses any local types.

- [ ] **Step 1.4: Run regression test**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_agent_download.py::test_enroll_email_schema_rebuild_does_not_raise -v
```

Expected: PASS.

- [ ] **Step 1.5: Run the full agent download test suite**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/test_agent_download.py -v
```

Expected: All pass.

- [ ] **Step 1.6: Smoke-test app import**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -c "from startup.app_factory import create_app; app = create_app(); print('OK')"
```

Expected: `OK` with no annotation errors.

- [ ] **Step 1.7: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add api/routers/agent_download.py api/tests/test_agent_download.py
git commit -m "fix(api): resolve PydanticUndefinedAnnotation in EnrollEmailRequest.Platform"
```

---

## Task 2: N1 — Run soak end-to-end

**Files:**
- Read: `scripts/soak/replay_traces.py` (already exists)
- Read: `docs/soak-test-runbook.md` (already exists)

The soak harness is at `scripts/soak/replay_traces.py`. After fixing the Pydantic bug, the harness should be importable. This task runs it end-to-end and documents findings.

- [ ] **Step 2.1: Verify soak script imports cleanly**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
python -c "import scripts.soak.replay_traces; print('OK')" 2>&1
# Or: python scripts/soak/replay_traces.py --help
```

If this still fails, fix the import error and commit a separate fix before continuing.

- [ ] **Step 2.2: Start a test API server**

In a separate terminal or background process, start the API server (requires Postgres). Verify it's accepting requests:

```bash
curl -s http://localhost:8000/health | head -20
```

- [ ] **Step 2.3: Run a short soak validation (5–10 min)**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
python scripts/soak/replay_traces.py \
  --api-url http://localhost:8000/api \
  --duration 600 \
  --output /tmp/soak-short \
  2>&1 | tee /tmp/soak-short.log
```

Check for fatal crashes. If the script runs cleanly for 10 minutes, proceed to the 24h run.

- [ ] **Step 2.4: Document findings after soak run**

After the soak completes (or after a minimum 10-minute validation), update `docs/soak-test-runbook.md` with:

```markdown
## Run History

| Date       | Duration | Fatal crashes | Notes |
|------------|----------|---------------|-------|
| 2026-03-24 | Xh       | 0             | Short validation run post N1.1 fix |
```

Also record any errors seen (with counts), latency observations, and rate-limit/retry behavior.

- [ ] **Step 2.5: Commit findings**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add docs/soak-test-runbook.md
git commit -m "docs(soak): record N1 soak validation run findings"
```

---

## Task 3: N2 — Lighthouse serve-and-measure harness

**Files:**
- Create: `scripts/lighthouse/run.sh`
- Modify: `docs/dashboard-performance.md`
- Create: `.github/workflows/lighthouse.yml`

- [ ] **Step 3.1: Verify Lighthouse CLI is available or installable**

```bash
npx lighthouse --version 2>&1 || echo "not installed"
```

If not installed: `npm install -g lighthouse` (or use `npx lighthouse` in the script).

- [ ] **Step 3.2: Create the harness script**

```bash
# scripts/lighthouse/run.sh
#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_DIR="$(cd "$(dirname "$0")/../../dashboard" && pwd)"
OUTPUT_DIR="${1:-/tmp/lighthouse-results}"
mkdir -p "$OUTPUT_DIR"

echo "Building dashboard..."
cd "$DASHBOARD_DIR"
npm run build

echo "Starting preview server..."
npx vite preview --port 4173 &
PREVIEW_PID=$!
trap "kill $PREVIEW_PID 2>/dev/null || true" EXIT

# Wait for server to be ready
sleep 3

echo "Running Lighthouse on core views..."
for ROUTE in "" "events" "sessions" "approvals" "exceptions"; do
  URL="http://localhost:4173/${ROUTE}"
  SLUG="${ROUTE:-dashboard}"
  echo "  Measuring $URL..."
  npx lighthouse "$URL" \
    --output json \
    --output-path "$OUTPUT_DIR/lighthouse-${SLUG}.json" \
    --chrome-flags="--headless --no-sandbox" \
    --quiet || echo "  WARNING: Lighthouse failed for $SLUG"
done

echo "Extracting key metrics..."
for RESULT_FILE in "$OUTPUT_DIR"/lighthouse-*.json; do
  SLUG=$(basename "$RESULT_FILE" .json | sed 's/lighthouse-//')
  if [ -f "$RESULT_FILE" ]; then
    SCORE=$(python3 -c "import json,sys; d=json.load(open('$RESULT_FILE')); print(d['categories']['performance']['score'])" 2>/dev/null || echo "N/A")
    FCP=$(python3 -c "import json,sys; d=json.load(open('$RESULT_FILE')); print(d['audits']['first-contentful-paint']['displayValue'])" 2>/dev/null || echo "N/A")
    LCP=$(python3 -c "import json,sys; d=json.load(open('$RESULT_FILE')); print(d['audits']['largest-contentful-paint']['displayValue'])" 2>/dev/null || echo "N/A")
    echo "  $SLUG: score=$SCORE FCP=$FCP LCP=$LCP"
  fi
done

echo "Results saved to $OUTPUT_DIR"
```

```bash
chmod +x scripts/lighthouse/run.sh
```

- [ ] **Step 3.3: Run the harness and capture baseline**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
bash scripts/lighthouse/run.sh /tmp/lighthouse-baseline
```

Record the output numbers (score, FCP, LCP) for each view.

- [ ] **Step 3.4: Update docs/dashboard-performance.md with real numbers**

Open `docs/dashboard-performance.md`. Replace the placeholder LCP/FCP rows with real values from the baseline run. Add a "Lighthouse Baseline" section:

```markdown
## Lighthouse Baseline (2026-03-24)

Captured on: Vite preview (production build), headless Chrome, localhost

| View        | Score | FCP    | LCP    |
|-------------|-------|--------|--------|
| /dashboard  | X.XX  | X.X s  | X.X s  |
| /events     | X.XX  | X.X s  | X.X s  |
| /sessions   | X.XX  | X.X s  | X.X s  |
| /approvals  | X.XX  | X.X s  | X.X s  |
| /exceptions | X.XX  | X.X s  | X.X s  |

## Budget Thresholds

| Metric          | Soft (warn) | Hard (fail CI) |
|-----------------|-------------|----------------|
| Performance     | < 0.70      | < 0.50         |
| LCP             | > 3.5 s     | > 5.0 s        |
| FCP             | > 2.0 s     | > 3.5 s        |
| Bundle chunk    | > 600 KB    | > 700 KB       |
```

- [ ] **Step 3.5: Create CI workflow**

```yaml
# .github/workflows/lighthouse.yml
name: Lighthouse Performance

on:
  pull_request:
    paths:
      - 'dashboard/src/**'
      - 'dashboard/package.json'
      - 'dashboard/vite.config.js'

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: dashboard/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Install Lighthouse
        run: npm install -g lighthouse

      - name: Start preview server
        run: npx vite preview --port 4173 &
        env:
          NODE_ENV: production

      - name: Wait for server
        run: sleep 5

      - name: Run Lighthouse
        run: |
          lighthouse http://localhost:4173/ \
            --output json \
            --output-path /tmp/lh-result.json \
            --chrome-flags="--headless --no-sandbox --disable-gpu" \
            --quiet

      - name: Check performance budget
        run: |
          python3 - <<'EOF'
          import json, sys
          d = json.load(open('/tmp/lh-result.json'))
          score = d['categories']['performance']['score']
          lcp_ms = d['audits']['largest-contentful-paint']['numericValue']
          fcp_ms = d['audits']['first-contentful-paint']['numericValue']

          warnings = []
          failures = []

          if score < 0.70:
            warnings.append(f"Performance score {score:.2f} < 0.70 (soft threshold)")
          if score < 0.50:
            failures.append(f"Performance score {score:.2f} < 0.50 (hard threshold)")
          if lcp_ms > 3500:
            warnings.append(f"LCP {lcp_ms:.0f}ms > 3500ms (soft threshold)")
          if lcp_ms > 5000:
            failures.append(f"LCP {lcp_ms:.0f}ms > 5000ms (hard threshold)")
          if fcp_ms > 2000:
            warnings.append(f"FCP {fcp_ms:.0f}ms > 2000ms (soft threshold)")
          if fcp_ms > 3500:
            failures.append(f"FCP {fcp_ms:.0f}ms > 3500ms (hard threshold)")

          for w in warnings:
            print(f"::warning::{w}")
          for f in failures:
            print(f"::error::{f}")

          if failures:
            sys.exit(1)
          print(f"Lighthouse budget OK: score={score:.2f} LCP={lcp_ms:.0f}ms FCP={fcp_ms:.0f}ms")
          EOF
```

- [ ] **Step 3.6: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add scripts/lighthouse/run.sh docs/dashboard-performance.md .github/workflows/lighthouse.yml
git commit -m "feat(ops): add Lighthouse baseline + CI budget gates (N2)"
```

---

## Task 4: N3 — Capability drift runbook + widget linkage

**Files:**
- Create: `docs/capability-drift-runbook.md`
- Modify: `dashboard/src/components/dashboard/CapabilityDriftWidget.jsx`

- [ ] **Step 4.1: Create capability-drift-runbook.md**

```markdown
# Capability Drift Runbook

Capability drift occurs when a monitored agent loses telemetry capabilities it previously provided — e.g., process enumeration, network monitoring, or file access tracking. Drift is detected by comparing current capability reports against the last known-good baseline.

## Severity Mapping

| Sessions with drift | Severity | Required response |
|---------------------|----------|-------------------|
| 1                   | Low      | Monitor; no immediate action required |
| 2                   | Medium   | Investigate root cause within 4 hours |
| 3+                  | High     | Escalate; treat as potential evasion; re-verify agent integrity |

## Analyst Response Path

### Low — 1 session with drift

1. Verify the endpoint is still reporting events (check Events page filtered by endpoint).
2. Check if the agent was recently restarted or upgraded.
3. If drift resolves on next scan cycle: no action. Document in detection review log.
4. If drift persists for 3+ cycles: escalate to Medium.

### Medium — 2 sessions with drift

1. Open endpoint detail. Verify last_seen timestamp is recent.
2. Check audit log for any recent policy, posture, or allow-list changes on this endpoint.
3. Attempt to contact endpoint owner. Verify agent version and OS service state.
4. If root cause confirmed benign (e.g., permission revoked by OS upgrade): document mitigation.
5. If no clear explanation: escalate to High.

### High — 3+ sessions with drift

1. Treat as potential evasion until cleared.
2. Review evasion_vectors in recent session reports for E1–E8 indicators.
3. If evasion is suspected: escalate to security incident response.
4. Consider moving endpoint posture to "active" to enforce stricter controls.
5. Document findings in the detection review log with decision.

## Measuring MTTR

Drift alert-to-action MTTR is measured from `first_drift_session.observed_at` to the timestamp of the analyst's documented resolution entry in the audit log or detection review log.

Target: < 4 hours for Medium, < 1 hour for High.

## References

- `docs/soc-analyst-workflow.md` — full triage pipeline
- `docs/detection-review-cadence.md` — weekly review process
- `docs/known-limitations.md` — known telemetry gaps
```

- [ ] **Step 4.2: Wire the "View runbook" link in CapabilityDriftWidget**

In `dashboard/src/components/dashboard/CapabilityDriftWidget.jsx`, find the "View runbook" button/link. Currently it likely links to a placeholder (`#`) or a non-existent path. Update it to link to the documentation:

```jsx
<a
  href="https://github.com/grislyevan/agentic-governance/blob/main/docs/capability-drift-runbook.md"
  target="_blank"
  rel="noopener noreferrer"
  className="text-xs text-detec-ui-accent hover:underline"
>
  View runbook
</a>
```

If the widget renders severity in text, verify the mapping matches the runbook table (Low/Medium/High → 1/2/3+ sessions). If there's a mismatch, update the widget's severity label logic to match.

- [ ] **Step 4.3: Verify dashboard tests pass**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 4.4: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add docs/capability-drift-runbook.md \
  dashboard/src/components/dashboard/CapabilityDriftWidget.jsx
git commit -m "docs+feat(ops): add capability-drift runbook and wire widget link (N3)"
```

---

## Task 5: Final verification

- [ ] **Step 5.1: Run API tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

- [ ] **Step 5.2: Run dashboard tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test 2>&1 | tail -20
```

- [ ] **Step 5.3: Smoke-test app import (confirms Pydantic fix holds)**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -c "from startup.app_factory import create_app; create_app(); print('OK')"
```
