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

1. **Security Tests** – API and collector security test suites.
2. **Static Analysis (Semgrep)** – SAST.
3. **Dependency Audit (Trivy)** or **Dependency Audit (pip-audit, npm audit)** – at least one dependency check (Trivy is broader; pip-audit/npm audit are stack-specific).
4. **Secrets Detection (Gitleaks)** – no committed secrets.

Branch protection is configured in the repo settings (Settings → Branches → Branch protection rules). This repo does not set it via API; configure these checks there so failing security workflow or security tests blocks merge when desired.

## Local runs

```bash
# API security tests (requires Postgres and env)
cd api && DATABASE_URL=... JWT_SECRET=... SEED_ADMIN_PASSWORD=... python -m pytest tests/test_security_pentest.py tests/test_gateway_security.py tests/test_rate_limits.py -v

# Collector security tests
pip install -e ".[dev]" && python -m pytest collector/tests/test_agent_security.py -v
```
