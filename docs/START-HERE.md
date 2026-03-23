# START HERE — Navigation Index

This is the canonical entry point for contributors, operators, and deployers. Pick your track below.

---

## Contributor Quick Path

First-time setup:

1. Clone the repo and run `make bootstrap-dev` from the repo root (installs the project with dev extras).
2. Run `detec scan --verbose` to verify the collector works.
3. Run `make help` to see all available targets.

Key references:

- [CONTRIBUTING.md](../CONTRIBUTING.md) — development setup, test commands, PR conventions
- [docs/local-test-profiles.md](local-test-profiles.md) — copy-paste test commands for three common local environments

---

## Operator / Pilot Path

Start here to evaluate Detec for a pilot or active deployment:

- [docs/product-status.md](product-status.md) — capability maturity, what is shipping vs. experimental
- [docs/pilot-runbook.md](pilot-runbook.md) — step-by-step pilot execution guide
- [docs/pilot-go-no-go-checklist.md](pilot-go-no-go-checklist.md) — go/no-go criteria before expanding a pilot

---

## Deployment Path

For production server setup and agent deployment:

- [SERVER.md](../SERVER.md) — server deployment, environment variables, first API key, security hardening
- [DEPLOY.md](../DEPLOY.md) — agent auto-start (LaunchAgent, systemd, Windows Task), MDM deployment
- [docs/architecture-overview.md](architecture-overview.md) — system architecture and component relationships

---

## Archival Docs

Session notes, sprint handoffs, and superseded design docs live in `docs/archive/`. These are historical records and are **not** updated after archival. Do not treat them as authoritative references.

See [docs/archive/README.md](archive/README.md) for the archival standard and the list of canonical docs by topic.
