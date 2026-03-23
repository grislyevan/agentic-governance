name: Security Architecture Narrative
acronym: SEN
satisfies:
  TSC:
    - CC6.6
    - CC6.7
    - CC7.1
    - CC7.2
    - CC7.3
    - CC7.4
majorRevisions:
  - date: Mar 11 2026
    comment: Customized for Detec
  - date: Jun 1 2018
    comment: Initial document
---

# Security Architecture Narrative

The following describes {{.Name}}'s security architecture and the controls in place to protect the confidentiality, integrity, and availability of customer data and the {{.Name}} platform.

# {{.Name}} Product Architecture

The {{.Name}} platform is a distributed system consisting of endpoint agents and a central server. Agents are deployed to customer workstations where they observe agentic AI tool activity. Events flow from agents to the central API over authenticated, encrypted channels (HTTPS or TLS-wrapped binary protocol). The central server processes events, evaluates policy, and presents findings through a SOC dashboard.

Key security properties of the architecture:

- **Read-only observation**: The endpoint agent never modifies, blocks, or interferes with detected AI tools. It collects metadata only.
- **Least-privilege agent**: The agent runs under standard user permissions. No root or administrator privileges are required for core scanning functionality.
- **Authenticated transport**: All agent-to-server communication requires a valid API key. HTTP transport uses HTTPS; the binary TCP protocol uses TLS.
- **Tenant isolation**: Each customer's data is logically isolated at the database and API layers. API keys and JWT tokens are scoped to individual tenants.

# {{.Name}} Infrastructure

## Product Infrastructure

The {{.Name}} central server is deployed as a containerized FastAPI application backed by PostgreSQL (production) or SQLite (development/testing). The application serves both the REST API and the React dashboard from a single process.

The DetecGateway component listens on a dedicated TCP port (8001) for high-throughput binary connections from agents using msgpack framing, enabling efficient telemetry ingestion at scale.

### Authorized Personnel

- **Production database** access is restricted to the CTO and designated SRE personnel
- **Server deployment** access is limited to authorized DevOps operators
- **Dashboard admin** access uses JWT authentication with role-based access control
- **Agent API keys** are provisioned per-tenant and can be rotated through the API

## IT Infrastructure

{{.Name}} uses the following services for internal infrastructure:

- **GitHub**: Source control, issue tracking, CI/CD (GitHub Actions)
- **Communication tools**: Team messaging and video conferencing
- **Cloud hosting**: Container orchestration and managed database services

Access to these services is limited according to role and is reviewed quarterly, as well as during onboarding/offboarding.

# {{.Name}} Workstations

{{.Name}} workstations are hardened against logical and physical attack by the following measures:

- Operating system must be within one generation of current
- Full-disk encryption enabled (FileVault on macOS, BitLocker on Windows, LUKS on Linux)
- Endpoint protection software installed and automatically updated
- OS and application updates applied promptly
- Screen lock required after inactivity

Workstation compliance is evaluated quarterly. {{.Name}} uses its own endpoint agent to monitor for unauthorized AI tool usage on corporate devices.

## Remote Access

{{.Name}} team members work remotely and connect to production and internal systems via encrypted channels (HTTPS, SSH with key-based authentication). VPN is used where additional network-level isolation is required. It is each team member's responsibility to ensure that only authorized personnel use {{.Name}} resources.

# Access Review

Access to {{.Name}} infrastructure, both internal and product, is reviewed quarterly. Inactive users are removed. Anomalies are reported to the security team for investigation. Onboarding and offboarding procedures ensure timely provisioning and deprovisioning of access.

# Penetration Testing

{{.Name}} commissions external penetration testing on an annual basis. Findings are reviewed immediately and remediated according to severity: critical and high findings within 48 hours, medium findings within 30 days, and low findings within 90 days.

# {{.Name}} Physical Security

{{.Name}} operates as a distributed team. Physical security controls focus on workstation hardening and encrypted storage. Where office space is used, key issuance is tracked and physical access is reviewed regularly.

Production infrastructure is hosted by cloud providers with SOC2-certified physical security controls. {{.Name}} does not maintain its own data center facilities.

# Risk Assessment

{{.Name}} updates its Cyber Risk Assessment on an annual basis. The following is an inventory of threats assessed to be relevant to {{.Name}}'s operations.

## Adversarial Threats

| Threat | Source | Vector | Target | Likelihood | Severity |
|--------|--------|--------|--------|------------|----------|
| API credential theft | External attacker | Phishing, credential stuffing | Central API | Medium | High |
| Agent impersonation | External attacker | Stolen API key | Event ingestion | Low | High |
| Supply chain attack | External attacker | Compromised dependency | Agent or API | Low | Critical |
| Insider data exfiltration | Malicious insider | Direct database access | Customer telemetry | Low | High |
| Dashboard session hijack | External attacker | XSS, CSRF | SOC dashboard | Low | Medium |

## Non-Adversarial Threats

| Threat | Vector | Target | Likelihood | Severity |
|--------|--------|--------|------------|----------|
| Cloud provider outage | Infrastructure failure | Central API availability | Low | High |
| Database corruption | Software bug, disk failure | Event data integrity | Low | High |
| Agent misconfiguration | Operator error | Detection coverage gaps | Medium | Medium |
| Dependency vulnerability | Unpatched library | Agent or API | Medium | Medium |

# References

## Narratives

- Products and Services Narrative
- System Architecture Narrative
- Control Environment Narrative

## Policies

- Encryption Policy
- Log Management Policy
- Remote Access Policy
- Security Incident Response Policy
- Workstation Policy
- Application Security Policy
- Password Policy

## Procedures

- Apply OS Patches
- Review Access
- Review Devices and Workstations
- Vulnerability Scan
