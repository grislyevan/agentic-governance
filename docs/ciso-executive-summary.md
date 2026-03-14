# CISO Executive Summary: Detec Agentic AI Governance

Detec provides endpoint detection and policy enforcement for agentic AI tools. Governance is grounded in a five-layer detection model (Process, File, Network, Identity, Behavior) and a deterministic policy engine with an enforcement ladder: Detect, Warn, Approval Required, and Block. The threat model in [docs/threat-model.md](threat-model.md) is validated and aligned with code and tests.

**Current posture.** Authentication (JWT and API key, including tenant agent key at the gateway), tenant isolation, event validation, and rate limiting are in place. The response orchestrator runs default playbooks on event ingest; tenant-defined playbooks are managed via the API but are not yet executed on ingest (finding F-005; product decision pending). Baseline policies are defined in [api/core/baseline_policies.py](../api/core/baseline_policies.py); details and open findings are in [docs/security-findings.md](security-findings.md).

**Coverage.** Fifteen baseline rules (6 enforcement, 3 Class D, 3 overlay, 3 fallback) are seeded per tenant. NET-001 and NET-002 are active; ISO-001 (container isolation) is advisory and inactive by default. The calibration harness and lab-run data support confidence bands. Security test suites (pentest, gateway, rate limits, collector) pass.

**Residual risk.** Overall risk remains low to medium. Open items are predominantly Low or Informational (config hygiene, gateway input limits, playbook schema depth, documentation). One Medium finding (F-005) depends on product intent for custom playbooks.

**Compliance.** Controls map to SOC 2 (CC6.1, CC7.2, CC8.1), ISO 27001 (A.12.6), and NIST CSF (ID.AM, DE.CM, RS.AN). The mapping is in [docs/compliance-mapping.md](compliance-mapping.md); evidence for audits will be gathered at review time.

**Next steps.** Resolve F-005 (document or implement custom playbook execution). Remediate F-007, F-006, and F-014 via the security engineer handoff described in the assessment scope section of [docs/security-findings.md](security-findings.md). Publish and maintain the compliance mapping and assessment-scope documentation. Schedule the next CISO review after the next major release (e.g. Class D expansion or container isolation implementation).
