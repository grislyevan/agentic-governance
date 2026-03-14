# Detec Compliance Mapping

This document maps Detec's detection and enforcement capabilities to common compliance frameworks so auditors and leadership can see control coverage. Evidence for specific audit requests (e.g. SOC 2 evidence) is gathered at review time; this doc describes the capabilities and where they live in the codebase.

---

## SOC 2

| Control | Detec capability | Reference |
|---------|------------------|-----------|
| **CC6.1** (Logical and physical access controls) | Identity layer (user/account mapping, code signatures, credential stores) and policy engine enforcement provide tool-level access governance. All sensitive API actions and enforcement decisions are scoped by tenant and role. Audit log records actor, action, resource, tenant. | [api/core/auth.py](../api/core/auth.py), [api/core/tenant.py](../api/core/tenant.py), [api/core/baseline_policies.py](../api/core/baseline_policies.py), [api/core/audit_logger.py](../api/core/audit_logger.py), [collector/engine/policy.py](../collector/engine/policy.py) |
| **CC7.2** (Monitoring) | Five-layer continuous detection (Process, File, Network, Identity, Behavior) plus daemon scanning and heartbeat liveness. Endpoint fleet monitoring with change detection; events and enforcement outcomes are recorded and queryable. | [collector/](../collector/), [api/routers/events.py](../api/routers/events.py), [api/routers/endpoints.py](../api/routers/endpoints.py) |
| **CC8.1** (Change management) | Behavior layer captures temporal action sequences (prompt-edit-commit loops) and git attribution. AI-assisted code change tracking and enforcement decisions are logged with rule ID, version, and evidence trace. | [collector/engine/confidence.py](../collector/engine/confidence.py), [api/core/audit_logger.py](../api/core/audit_logger.py), [docs/threat-model.md](threat-model.md) |

---

## ISO 27001

| Control | Detec capability | Reference |
|---------|------------------|-----------|
| **A.12.6** (Technical vulnerability management) | Confidence scoring and enforcement ladder (Detect, Warn, Approval Required, Block) provide risk-scored detection with proportional response. Calibration harness and lab-run data validate confidence bands; policy engine applies deterministic rules. | [collector/engine/confidence.py](../collector/engine/confidence.py), [collector/engine/policy.py](../collector/engine/policy.py), [api/core/baseline_policies.py](../api/core/baseline_policies.py), [collector/tests/test_calibration.py](../collector/tests/test_calibration.py) |

---

## NIST CSF

| Control | Detec capability | Reference |
|---------|------------------|-----------|
| **ID.AM** (Asset management) | Process and File layers plus tool classification (Class A/B/C/D) provide agentic AI tool inventory with capability classification. Endpoints and detected tools are tracked per tenant. | [collector/scanner/](../collector/scanner/), [api/core/baseline_policies.py](../api/core/baseline_policies.py), [api/models/endpoint.py](../api/models/endpoint.py) |
| **DE.CM** (Detection, continuous monitoring) | Daemon mode scanning and change-only reporting provide continuous endpoint telemetry. Heartbeat and event ingest support efficient reporting; gateway and HTTP ingest both validate and persist events. | [collector/main.py](../collector/main.py), [api/gateway.py](../api/gateway.py), [api/routers/events.py](../api/routers/events.py) |
| **RS.AN** (Analysis) | Cross-layer correlation and explainability payload (rule ID, version, contributing signals, penalties, evidence IDs) support evidence-based enforcement and full audit trail. | [collector/engine/policy.py](../collector/engine/policy.py), [api/core/audit_logger.py](../api/core/audit_logger.py), [docs/threat-model.md](threat-model.md) |

---

## Gaps and evidence notes

1. **Agent key rotation/revocation:** No formal key rotation or revocation workflow for the tenant agent key is implemented. Threat model mitigation #13 documents this; operations must handle rotation manually. Evidence for "logical access" may require runbooks or procedures outside this codebase.

2. **Container isolation (ISO-001):** The baseline rule ISO-001 (container isolation for Class C) ships inactive and is advisory until a dedicated implementation exists. Runtime containerization of already-running processes is not implemented. See [api/core/baseline_policies.py](../api/core/baseline_policies.py) and [docs/enforcement-roadmap.md](enforcement-roadmap.md).

3. **Evidence from production:** Controls that require "evidence from production" (e.g. SOC 2 evidence requests, sample logs, access reviews) must be supplied at audit time. This document describes capabilities and code references; it does not substitute for evidence collection.
