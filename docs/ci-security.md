# CI Security

This document describes security-related jobs in CI and recommended branch-protection settings for `main`.

## Security jobs

| Job name | Workflow | What it runs |
|----------|----------|--------------|
| **Security Tests** | [.github/workflows/security.yml](../.github/workflows/security.yml) | API security tests (pentest, gateway security, rate limits) and collector agent security tests. Uses same Postgres and env as API tests. |
| **Static Analysis (Semgrep)** | security.yml | Semgrep with OWASP Top 10, CWE Top 25, Python, and JavaScript rules. |
| **Dependency Audit (Trivy)** | security.yml | Trivy filesystem scan. Fails on CRITICAL or HIGH severity. Exit code 1 on findings. |
| **Dependency Audit (pip-audit, npm audit)** | security.yml | pip-audit for Python (collector + API); npm audit with `--audit-level=moderate` for dashboard. |
| **Secrets Detection (Gitleaks)** | security.yml | Scans for hardcoded secrets in the repo. |

Other CI jobs (e.g. API Tests, Collector Tests) include security test files because they run the full test suites; the **Security Tests** job exists so you can require a single named check for branch protection.

## SAST/SCA behavior

- **Semgrep:** Config includes `p/owasp-top-ten`, `p/cwe-top-25`, `p/python`, `p/javascript`. Add or change rules in the workflow or via a `.semgrep.yml` in the repo.
- **Trivy:** `severity: CRITICAL,HIGH`; job exits with code 1 if any such finding exists. Adjust in security.yml if you need to allow HIGH or change severity.
- **npm audit:** `npm audit --audit-level=moderate`; fails on moderate and above. Change `--audit-level` in security.yml to tune (e.g. `high` or `critical` only).

## Recommended required status checks for `main`

Configure branch protection in GitHub so that the following (or equivalent) must pass before merging to `main`:

**Test and build gates (CI workflow):**

1. **Build Dashboard** – dashboard build (npm ci + npm run build).
2. **Collector Tests** – `pytest collector/tests/` (excluding benchmark/slow).
3. **Protocol Tests** – `pytest protocol/tests/`.
4. **API Tests** – `pytest api/tests/` (requires Postgres; run in CI with service).

**Security workflow:**

5. **Security Tests** – API and collector security test suites.
6. **Static Analysis (Semgrep)** – SAST.
7. **Dependency Audit (Trivy)** or **Dependency Audit (pip-audit, npm audit)** – at least one dependency check (Trivy is broader; pip-audit/npm audit are stack-specific).
8. **Secrets Detection (Gitleaks)** – no committed secrets.

Branch protection is configured in the repo settings (Settings → Branches → Branch protection rules). This repo does not set it via API; configure these checks there so failing CI or security workflow blocks merge when desired.

## Test split and how to run tests (contributors)

**Bootstrap (run once):** From repo root, run `make bootstrap-dev`. This installs the project in editable mode with dev extras (pytest and plugins) and API dependencies so all three test suites can run without missing dependency surprises.

Tests are split by package to avoid import and path conflicts:

| Suite | Path | How to run from repo root |
|-------|------|---------------------------|
| Collector | `collector/tests/` | `make test-collector` or after `make bootstrap-dev`: `python -m pytest collector/tests/ -m 'not benchmark and not slow' -x -q` |
| API | `api/tests/` | `make test-api` or after bootstrap, from repo root: `cd api && python -m pytest tests/ -m 'not benchmark and not slow' -x -q` (requires `DATABASE_URL`, `JWT_SECRET`, `SEED_ADMIN_PASSWORD`) |
| Protocol | `protocol/tests/` | `make test-protocol` or after `make bootstrap-dev`: `python -m pytest protocol/tests/ -q` |

**Single path to run all suites:** From repo root, run `make bootstrap-dev` once, then `make test-all-safe`. API tests require a running Postgres and env vars (see [.github/workflows/ci.yml](../.github/workflows/ci.yml) for CI env). For dashboard build only: `make build-dashboard`.

## Dependency and vulnerability hygiene

- **Cadence:** Run dependency audits at least weekly. CI runs Trivy, pip-audit, and npm audit on every push/PR to main; findings block merge when severity is CRITICAL or HIGH (see security.yml).
- **Optional:** A scheduled workflow (e.g. weekly) can run audits and open or update a GitHub Issue when new findings appear; document that workflow here if added.

## Local runs

```bash
# API security tests (requires Postgres and env)
cd api && DATABASE_URL=... JWT_SECRET=... SEED_ADMIN_PASSWORD=... python -m pytest tests/test_security_pentest.py tests/test_gateway_security.py tests/test_rate_limits.py -v

# Collector security tests
pip install -e ".[dev]" && python -m pytest collector/tests/test_agent_security.py -v

# Evasion suite (INIT-31; optional or nightly). Full instructions: docs/evasion-suite.md
python -m pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -v
```
