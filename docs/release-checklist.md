# Release checklist

Use this checklist before cutting a release (tag and/or production deploy). All items should be satisfied; CI and security scans are the source of truth.

**Last updated:** Sprint 4 (Big-Ole Remediation Program)

---

## Pre-release

- [ ] **Version and changelog:** Bump version in `pyproject.toml` (and any other version pins). Update `CHANGELOG.md` or release notes with user-visible changes.
- [ ] **Security findings:** Confirm [docs/SECURITY-TECHNICAL-REPORT.md](SECURITY-TECHNICAL-REPORT.md) and [docs/hardening-checklist.md](hardening-checklist.md) are current; no open critical/high without owner and sprint.

---

## CI gates (must pass)

Merge to `main` and the release branch must have all of the following green:

| Job | Workflow | Purpose |
|-----|----------|---------|
| Build Dashboard | [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Dashboard builds successfully |
| Collector Tests | ci.yml | `pytest collector/tests/` (excl. benchmark/slow) |
| Protocol Tests | ci.yml | `pytest protocol/tests/` |
| API Tests | ci.yml | `pytest api/tests/` (Postgres service) |
| Calibration Regression | ci.yml | Calibration replay harness |
| Security Tests | [.github/workflows/security.yml](../.github/workflows/security.yml) | API and collector security test suites |
| Static Analysis (Semgrep) | security.yml | SAST |
| Dependency Audit (Trivy and/or pip-audit, npm audit) | security.yml | No CRITICAL/HIGH unmitigated |
| Secrets Detection (Gitleaks) | security.yml | No committed secrets |

See [docs/ci-security.md](ci-security.md) for branch protection and local runs.

---

## Post-release

- [ ] Tag created and pushed (e.g. `v0.2.0`). If using GitHub Releases, attach build artifacts or link to install instructions.
- [ ] [docs/release-checklist.md](release-checklist.md): Note that this checklist was used for the release (e.g. "Used for v0.2.0 on YYYY-MM-DD").
- [ ] Notify stakeholders if applicable; update deployment runbooks if config or env changed.

---

## Dependency and vulnerability hygiene

- **Cadence:** Run dependency audits at least weekly (e.g. `pip-audit`, `npm audit`, Trivy). CI runs these on every push/PR; for release, ensure no new CRITICAL/HIGH have been introduced since the last release.
- **Automation:** Optionally add a scheduled workflow (e.g. weekly) that runs audits and opens or updates a GitHub Issue when findings appear. Document in [docs/ci-security.md](ci-security.md) if added.
