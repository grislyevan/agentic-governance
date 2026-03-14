# Threat Model Task List

Derived from the threat model plan. Use this with the orchestrator: Security Engineer implements, Code Reviewer (or EvidenceQA) validates doc vs code/tests.

- [x] 1. System overview and trust boundaries
- [x] 2. STRIDE: API and Gateway
- [x] 3. STRIDE: Collector
- [x] 4. STRIDE: Dashboard
- [x] 5. STRIDE: Playbook/orchestrator
- [x] 6. Attack surface list
- [x] 7. Key scenarios (agent compromise, API key compromise, tenant isolation)
- [x] 8. Mitigation table
- [x] 9. Review: validate doc references real code paths and tests; STRIDE/mitigations align with [api/core/auth.py](../api/core/auth.py), [api/gateway.py](../api/gateway.py), [api/core/response_orchestrator.py](../api/core/response_orchestrator.py) (validated auth, gateway, orchestrator refs and ran security suites on Mac).

**Deliverable:** [docs/threat-model.md](../docs/threat-model.md)
