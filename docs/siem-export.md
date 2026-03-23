# SIEM Export and Event Forwarding

**Workstream 6.** Detec events use a canonical JSON schema suitable for SIEM ingestion. This doc describes how to forward events to a SIEM and provides a proof path.

## Event schema

Events ingested via `POST /api/events` and stored in the Detec backend conform to the canonical event schema (see `schemas/`). Fields include:

- `event_type`, `tool_name`, `tool_class`, `confidence`
- `policy` (decision_state, rule_id, reason_codes)
- `endpoint` (id, hostname, os)
- `timestamp`, `trace_id`, tenant and actor identifiers

The schema is designed for direct SIEM ingestion: strict enums for decision-critical fields, flat structure where possible. See playbook and `schemas/event-schema.json` for the full definition.

## Export paths

### 1. Webhook to HTTP endpoint (Splunk HEC, generic HTTP)

Configure a webhook in Detec (dashboard or API) that sends each event (or enforcement event) to an HTTP endpoint. For Splunk:

- **Splunk HEC:** Use the HTTP Event Collector URL as the webhook target. Set method POST, and add the HEC token in the webhook headers (e.g. `Authorization: Splunk <token>`). Payload is the event JSON.
- **Generic SIEM:** Many SIEMs accept JSON over HTTP; use the same webhook with the SIEM’s ingestion URL and required headers.

Reference: [docs/enforcement-roadmap.md](enforcement-roadmap.md) (Splunk HEC mentioned in webhook templates).

### 2. Syslog (future or custom)

A syslog export can be added that formats each event as CEF or JSON and sends to a syslog server. Not implemented in tree; design would be: background worker or hook on event write that pushes to a configurable syslog host/port.

### 3. API pull

SIEMs that support "pull" can poll `GET /api/events` (with auth and tenant scope) and sync events. Rate limits and pagination apply; see API docs.

## Proof run

1. **Webhook:** Create a webhook in Detec pointing to a test HTTP endpoint (e.g. webhook.site or internal Splunk HEC). Trigger an event (e.g. run collector with dry-run and emit one event to the API). Confirm the webhook fires and the payload contains the full event.
2. **Document:** Record the webhook config (URL, headers) and a sample payload in this doc or in [docs/webhook-recipes.md](webhook-recipes.md) if that file exists.

## Security

- Do not log or forward raw credentials. Webhook secrets (e.g. HEC token) should be stored in server config or secrets manager and passed in headers, not in the event body.
- Tenant isolation: only events for the tenant that owns the webhook should be sent; the API must enforce this when dispatching webhooks.
