name: Products and Services Narrative
acronym: PSN
satisfies:
  TSC:
    - CC3.4
    - CC9.1
majorRevisions:
  - date: Mar 11 2026
    comment: Customized for Detec
  - date: Jun 1 2018
    comment: Initial document
---

# Products Narrative

The following describes the products and services marketed by {{.Name}}.

# Products

## Detec Endpoint Agent

The Detec Endpoint Agent is a lightweight Python-based collector that runs on macOS, Linux, and Windows workstations. It scans for the presence and activity of agentic AI tools (Claude Code, Cursor, Ollama, GitHub Copilot, and others), scores detection confidence using a calibrated engine, evaluates detections against policy rules, and reports events to the central API.

### Architecture

The agent consists of:

- **Scanners**: Modular detection routines for each supported AI tool (process, file, network, and environment signals)
- **Confidence Engine**: Weighted scoring system calibrated against lab-run fixtures, producing a 0-100 confidence score per detection
- **Policy Evaluator**: Compares detections against tenant-configured policy rules (15 baseline rules from the governance playbook)
- **Emitters**: HTTP (REST) and TCP (binary msgpack protocol) transports for sending events to the central API
- **Telemetry Providers**: Pluggable system for collecting process, network, and filesystem events (polling-based today; native OS providers planned)
- **Config Loader**: Supports JSON config files, environment variables (`AGENTIC_GOV_*`), and CLI flags

The agent can run as a one-shot scan or as a daemon with configurable intervals. It supports dry-run mode for validation without API connectivity.

### Security Considerations

- The agent runs with standard user privileges; no root/admin required for basic scanning
- API keys authenticate the agent to the central server and are stored in the local config (not embedded in source)
- All API communication uses HTTPS (HTTP transport) or TLS (TCP transport)
- The agent does not modify, block, or interfere with detected tools; it is read-only and observational
- Agent auto-start is managed via OS-native mechanisms (LaunchAgent, systemd, Windows Scheduled Task)

## Detec Central Server (API + Dashboard)

The central server is a FastAPI application that receives events from agents, manages policies, and serves the SOC dashboard.

### Architecture

- **FastAPI Backend**: RESTful API with JWT and API-key authentication, tenant isolation, invite tokens, password reset, and webhook integrations
- **DetecGateway**: Binary protocol gateway on port 8001 for high-throughput TCP connections from agents using msgpack framing
- **React Dashboard**: Vite-built SOC UI served by FastAPI, providing real-time visibility into detections, endpoints, and policy compliance
- **Database**: SQLite (development) or PostgreSQL (production), with baseline policies seeded per tenant on creation
- **EDR Enrichment**: Server-side integration pipeline for enriching detections with EDR telemetry (CrowdStrike Falcon and others)

### Security Considerations

- JWT-based authentication with configurable secret (`JWT_SECRET` environment variable)
- API-key authentication for agent-to-server communication
- Tenant isolation at the database level
- Baseline policy rules are `is_baseline=True`, cannot be deleted, and can be restored to defaults
- Rate limiting and input validation on all public endpoints
- Production deployments require `ENV=production` and strong secrets
- The dashboard enforces role-based access control

# References

## Narratives

- Organizational Narrative
- Security Architecture Narrative
- System Architecture Narrative
- Control Environment Narrative

## Policies

- Application Security Policy
- Software Development Lifecycle Policy
- Encryption Policy
- Log Management Policy
- Password Policy
- Security Incident Response Policy

## Procedures

- Apply OS Patches
- Review Access
- Vulnerability Scan
