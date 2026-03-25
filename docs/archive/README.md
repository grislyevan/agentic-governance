# Archived Documentation

Docs moved here are historical records — sprint handoffs, superseded design docs, and session notes. They are **not** updated after archival. Do not treat them as authoritative references. For current authoritative documentation, use the canonical docs listed below.

---

## Canonical Docs by Topic

| Topic | Authoritative Document |
|-------|----------------------|
| Architecture | [docs/architecture-overview.md](../architecture-overview.md) |
| CI / Security | [docs/ci-security.md](../ci-security.md) |
| Deployment | [DEPLOY.md](../../DEPLOY.md), [SERVER.md](../../SERVER.md) |
| Detection / Calibration | [docs/behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md), [docs/calibration-metrics.md](../calibration-metrics.md) |
| Enforcement | [docs/enforcement-safety-matrix.md](../enforcement-safety-matrix.md) |
| Dashboard | [docs/dashboard-roadmap.md](../dashboard-roadmap.md) |
| Lab Runs | [docs/lab-runs-and-results.md](../lab-runs-and-results.md), [PROGRESS.md](../../PROGRESS.md) |
| Product Status | [docs/product-status.md](../product-status.md) |
| Pilot Execution | [docs/pilot-runbook.md](../pilot-runbook.md), [docs/pilot-go-no-go-checklist.md](../pilot-go-no-go-checklist.md) |

---

## What Belongs in Archive

The following types of documents belong in `docs/archive/`:

- Sprint handoffs and end-of-sprint summaries
- Superseded architecture decisions (ADRs that have been replaced by a newer decision)
- Session notes and working documents that were used during a sprint but are no longer the authoritative reference
- Draft docs that were replaced by a finalized version in the main docs tree
- Design proposals that were rejected or substantially revised before implementation

Do not archive: active runbooks, current playbooks, or any doc still referenced as authoritative from `docs/START-HERE.md` or `README.md`.

---

## How to Archive

1. Create a dated subdirectory: `docs/archive/YYYY-MM-DD-<short-description>/`
2. Copy (do not move) the file into that subdirectory.
3. Add a header block at the top of the archived copy:

   ```
   ---
   ARCHIVED: YYYY-MM-DD
   Superseded by: <path to current authoritative doc>
   Reason: <one sentence>
   ---
   ```

4. The original file location may be deleted or left in place with a pointer to the archive copy, depending on whether other docs reference it. Prefer leaving a pointer rather than breaking links.
5. Note the archival in the relevant sprint handoff or in the commit message.
