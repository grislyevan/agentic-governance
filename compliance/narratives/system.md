name: System Architecture Narrative
acronym: SAN
satisfies:
  TSC:
    - CC6.1
    - CC6.4
    - CC6.5
    - A1.1
    - A1.2
    - A1.3
majorRevisions:
  - date: Mar 11 2026
    comment: Customized for Detec
  - date: Jun 1 2018
    comment: Initial document
---

# System Architecture Narrative

The following describes the system architecture of {{.Name}} and the technical controls that protect the confidentiality, integrity, and availability of the platform.

# System Overview

The {{.Name}} platform consists of three primary subsystems:

1. **Endpoint Agent (Collector)**: A Python-based daemon deployed to customer workstations that scans for agentic AI tools, scores confidence, evaluates policy, and emits events.
2. **Central API**: A FastAPI backend that ingests events, manages tenants/policies/users, enriches detections with EDR data, and serves the dashboard.
3. **SOC Dashboard**: A React/Vite single-page application providing real-time visibility into detections, endpoint health, and policy compliance.

## Data Flow

```
Endpoint Agent --> HTTPS POST /api/events --> FastAPI --> PostgreSQL
                   or
Endpoint Agent --> TLS TCP :8001 (msgpack) --> DetecGateway --> PostgreSQL
                                                                    |
                                              React Dashboard <-- FastAPI
```

Events flow from agents to the central server over authenticated encrypted channels. The API processes, stores, and indexes events. The dashboard queries the API to present findings to SOC analysts.

# Logical Access Controls

## Agent Authentication

- Each agent authenticates to the central API using a per-tenant API key passed in the `X-API-Key` header (HTTP) or in the handshake frame (TCP binary protocol)
- API keys are generated during tenant provisioning and can be rotated via the management API
- Invalid or expired keys result in immediate connection rejection

## Dashboard Authentication

- Users authenticate to the dashboard via JWT tokens issued by the `/api/auth/login` endpoint
- Passwords are hashed with bcrypt before storage
- JWT tokens have configurable expiration and are signed with a per-deployment secret (`JWT_SECRET`)
- Invite tokens enable controlled user onboarding with email verification
- Password reset flows use time-limited tokens

## Role-Based Access Control

- Dashboard users are assigned roles (admin, analyst, viewer) that govern API endpoint access
- Baseline policy rules cannot be deleted by any user (enforced at the API layer)
- Tenant isolation ensures users can only access data belonging to their organization

# Physical Access

{{.Name}} does not operate physical data center facilities. Production infrastructure runs on cloud providers with SOC2-certified physical security. Access to cloud management consoles is restricted to authorized operators with MFA enabled.

# Data Disposal

- Deleted records are soft-deleted by default, with hard deletion after a configurable retention period
- Database backups are encrypted and subject to the same retention and disposal policies
- Agent data on endpoints is ephemeral (ring buffer) and does not persist across agent restarts unless configured for local caching

# Capacity Planning

- The central API is horizontally scalable behind a load balancer
- The DetecGateway handles concurrent TCP connections using async I/O
- Database capacity is monitored with alerts for storage utilization thresholds
- Agent polling intervals are configurable per-deployment to control ingestion volume

# Backup and Recovery

- PostgreSQL databases are backed up daily with point-in-time recovery capability
- Backups are encrypted at rest and stored in a separate availability zone
- Application configuration and infrastructure definitions are version-controlled in Git
- Container images are stored in a private registry with immutable tags

# Recovery Testing

- Backup restoration is tested quarterly to verify data integrity and recovery time
- The recovery procedure is documented and includes database restore, API redeployment, and dashboard rebuild steps
- Recovery time objective (RTO): 4 hours. Recovery point objective (RPO): 24 hours.

# References

## Narratives

- Security Architecture Narrative
- Products and Services Narrative
- Control Environment Narrative

## Policies

- Application Security Policy
- Datacenter Security Policy
- Encryption Policy
- System Availability Policy
- Disaster Recovery Policy
