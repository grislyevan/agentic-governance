name: Control Environment Narrative
acronym: CEN
satisfies:
  TSC:
    - CC2.1
    - CC2.2
    - CC2.3
    - CC4.1
    - CC4.2
    - CC5.1
    - CC5.2
    - CC5.3
majorRevisions:
  - date: Mar 11 2026
    comment: Customized for Detec
  - date: Jun 1 2018
    comment: Initial document
---

# Control Environment Narrative

The following provides a description of the control structure of {{.Name}}.

The intent of this description is to enumerate the logical, policy, and procedural controls that serve to monitor {{.Name}}'s application and data security. Changes uncovered by these procedures in the logical, policy, procedural, or customer environment are addressed by remediations specific to the noted change.

# Logical Controls

{{.Name}} employs several logical controls to protect confidential data and ensure normal operation of the Detec platform:

- Mandatory data encryption at rest (database, backups) and in transit (HTTPS/TLS)
- JWT-based authentication with bcrypt password hashing for dashboard access
- API-key authentication for agent-to-server communication
- Tenant isolation at the database and API layers
- Role-based access control (admin, analyst, viewer) for dashboard operations
- Baseline policy rules that cannot be deleted (only deactivated or restored to defaults)
- Ring-buffer telemetry storage on agents to limit local data exposure
- Automated CI/CD pipeline with test suites (233 collector, 122 API, 45 protocol tests)
- Calibration regression harness that validates detection accuracy on every push to main

# Policy Controls

{{.Name}} employs several policy controls to protect confidential data and ensure normal operation of the Detec platform. These policies include:

- Access Onboarding and Termination Policy
- Application Security Policy
- Encryption Policy
- Log Management Policy
- Password Policy
- Remote Access Policy
- Security Incident Response Policy
- Software Development Lifecycle Policy
- Vendor Management Policy
- Workstation Policy

# Procedural Controls

{{.Name}} has scheduled procedures to monitor and tune the effectiveness of ongoing security controls, and event-driven procedures to respond to security-related events.

## Scheduled Security and Audit Procedures

- Review Access [quarterly]
- Review Security Logs [weekly]
- Review Cyber Risk Assessment [quarterly]
- Review Data Classification [quarterly]
- Backup Testing [quarterly]
- Disaster Recovery Testing [semi-annual]
- Review Devices and Workstations [quarterly]
- Review and Clear Low-Priority Alerts [weekly]
- Apply OS Patches [monthly]
- Verify Data Disposal per Retention Policy [quarterly]
- Conduct Security Training [annual]
- Review Security Monitoring and Alerting Configuration [quarterly]
- Penetration Test [annual]
- Vulnerability Scan [monthly]
- Agent Detection Calibration Review [quarterly]
- SOC2 Audit [annual]

## Event-Driven Security and Audit Procedures

- Onboard Employee
- Offboard Employee
- Investigate Security Alert
- Investigate Security Incident
- Rotate Compromised API Keys
- Respond to Agent Tampering Detection

# Remediations

{{.Name}} uses the outcomes of the aforementioned controls and procedures to identify shortcomings in the existing control environment. Once identified, shortcomings are remediated by improving existing controls and procedures, and creating new controls and procedures as needed. Remediation items are tracked as GitHub Issues with severity labels and assigned owners.

# Communications

{{.Name}} communicates relevant information regarding the functioning of the above controls with internal and external parties on an as-needed basis and according to statutory requirements.

## Internal

{{.Name}} communicates control outcomes, anomalies, and remediations internally using the following channels:

- Team messaging (Slack or equivalent)
- Email
- GitHub Issues and pull requests
- Weekly engineering syncs

## External

{{.Name}} communicates relevant control-related information to external parties including customers, contractors, regulators, and auditors as needed according to contractual and regulatory obligations. Security advisories are published to affected customers within 72 hours of confirmed incidents.
