# Webhook Recipes: SOC Integration Examples

Detec fires HMAC-signed webhooks for enforcement events so your SOC can integrate with PagerDuty, Slack, Jira, ServiceNow, Splunk, and other tools. All webhooks include the `X-Detec-Signature` header (HMAC-SHA256) for payload verification and `X-Detec-Delivery-Id` for idempotency.

## Enforcement Event Types Reference

| Event Type | Trigger | Suggested Severity |
|---|---|---|
| `enforcement.applied` | Agent enforced a block decision | High (PagerDuty P2) |
| `enforcement.simulated` | Audit mode: would have enforced | Info (Slack) |
| `enforcement.allow_listed` | Enforcement skipped (allow-list match) | Info (log only) |
| `enforcement.rate_limited` | Rate limiter suppressed enforcement | High (PagerDuty P2) |
| `enforcement.escalated` | Anti-resurrection escalation | Critical (PagerDuty P1) |
| `enforcement.failed` | Enforcement tactic failed | Critical (PagerDuty P1) |
| `posture.changed` | Admin changed endpoint posture | Medium (Slack/ticket) |

## Example Payload

A complete `enforcement.applied` webhook payload:

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "enforcement.applied",
  "observed_at": "2026-03-11T03:14:22Z",
  "tenant_id": "tenant-uuid",
  "endpoint": { "hostname": "prod-db-01", "posture": "active" },
  "tool": { "name": "Unknown Agent", "class": "C", "attribution_confidence": 0.82 },
  "policy": { "decision_state": "block", "rule_id": "ENFORCE-004" },
  "enforcement": {
    "tactic": "process_kill",
    "success": true,
    "pids_killed": [12345, 12346, 12347],
    "process_name": "python3",
    "cmdline_snippet": "python3 agent.py --target prod-db",
    "rate_limited": false,
    "simulated": false,
    "allow_listed": false,
    "provider": "local"
  },
  "severity": { "level": "S3" },
  "delivered_at": "2026-03-11T03:14:23Z"
}
```

## PagerDuty Recipe

**Event type triggers:** `enforcement.applied`, `enforcement.failed`, `enforcement.escalated`, `enforcement.rate_limited`

Use an intermediary (n8n, Zapier, AWS Lambda, or a small webhook receiver) to transform Detec webhooks into PagerDuty Events API v2 payloads.

### Payload mapping

| Detec field | PagerDuty field |
|---|---|
| `event_id` | `dedup_key` (deduplicates related alerts) |
| `severity.level` S3/S4 | `payload.severity` `critical` |
| `severity.level` S1/S2 | `payload.severity` `error` |
| `event_type` + `endpoint.hostname` + `tool.name` | `payload.summary` |
| `endpoint.hostname` | `payload.source` |
| `observed_at` | `payload.timestamp` |
| Full Detec payload | `payload.custom_details` |

### Severity mapping

| Detec severity | PagerDuty severity | PagerDuty urgency |
|---|---|---|
| S3, S4 | `critical` | High (P2) |
| S1, S2 | `error` | High (P2) |
| `enforcement.failed`, `enforcement.escalated` | `critical` | High (P1) |

### Events API v2 example

```json
{
  "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY",
  "dedup_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_action": "trigger",
  "payload": {
    "summary": "enforcement.applied: prod-db-01 blocked Unknown Agent (rule ENFORCE-004)",
    "severity": "critical",
    "source": "prod-db-01",
    "timestamp": "2026-03-11T03:14:22Z",
    "custom_details": {
      "event_type": "enforcement.applied",
      "tool_name": "Unknown Agent",
      "rule_id": "ENFORCE-004",
      "tactic": "process_kill",
      "pids_killed": [12345, 12346, 12347]
    }
  }
}
```

### curl test

```bash
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "routing_key": "YOUR_PAGERDUTY_INTEGRATION_KEY",
    "event_action": "trigger",
    "payload": {
      "summary": "Detec test: enforcement.applied on prod-db-01",
      "severity": "critical",
      "source": "prod-db-01"
    }
  }'
```

### HMAC verification (Python)

```python
import hashlib
import hmac

def verify_detec_webhook(body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
```

**Security note:** Never log the webhook secret. Rotate secrets regularly via the Detec dashboard or API.

## Slack Recipe

**Event type triggers:** `enforcement.simulated`, `posture.changed`

Use an Incoming Webhook or Slack app to post formatted messages. Configure the webhook URL in your intermediary (n8n, Zapier, or custom receiver).

### Block Kit message payload

```json
{
  "blocks": [
    {
      "type": "header",
      "text": { "type": "plain_text", "text": "Detec: enforcement.simulated", "emoji": true }
    },
    {
      "type": "section",
      "fields": [
        { "type": "mrkdwn", "text": "*Endpoint:*\nprod-db-01" },
        { "type": "mrkdwn", "text": "*Tool:*\nUnknown Agent (Class C)" },
        { "type": "mrkdwn", "text": "*Rule:*\nENFORCE-004" },
        { "type": "mrkdwn", "text": "*Tactic:*\nprocess_kill (simulated)" }
      ]
    },
    {
      "type": "context",
      "elements": [
        { "type": "mrkdwn", "text": "Audit mode: would have enforced. No action taken." }
      ]
    }
  ]
}
```

### Webhook URL configuration

1. Create a Slack Incoming Webhook (Settings > Integrations > Incoming Webhooks).
2. Point your intermediary at the webhook URL (e.g. `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX`).
3. Subscribe the Detec webhook to `enforcement.simulated` and `posture.changed` only, or route via your intermediary.

## Jira / ServiceNow Recipe

**Event type triggers:** `enforcement.applied`, `enforcement.escalated`

Jira and ServiceNow do not accept arbitrary webhooks directly. Use an intermediary (n8n, Zapier, custom Lambda, or webhook receiver) to transform Detec webhooks into Jira REST API calls.

### Field mapping for ticket creation

| Detec field | Jira field |
|---|---|
| `event_type` + `endpoint.hostname` + `tool.name` | `summary` |
| `event_id` | `description` (or custom field for correlation) |
| `endpoint.hostname` | Custom field `Endpoint` |
| `tool.name` | Custom field `Tool` |
| `policy.rule_id` | Custom field `Rule ID` |
| `enforcement.tactic` | Custom field `Tactic` |
| `severity.level` | `priority` (map S3/S4 to High, S1/S2 to Medium) |

### Jira REST API example

```bash
curl -X POST https://your-domain.atlassian.net/rest/api/3/issue \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JIRA_API_TOKEN" \
  -d '{
    "fields": {
      "project": { "key": "SEC" },
      "summary": "Detec enforcement.applied: prod-db-01 blocked Unknown Agent",
      "description": {
        "type": "doc",
        "version": 1,
        "content": [{
          "type": "paragraph",
          "content": [{ "type": "text", "text": "Event ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890" }]
        }]
      },
      "issuetype": { "name": "Incident" },
      "priority": { "name": "High" }
    }
  }'
```

## Splunk HEC Recipe

**Event type triggers:** All enforcement events (forward everything for SIEM correlation)

Forward all Detec enforcement webhooks to Splunk HTTP Event Collector (HEC) for indexing and correlation with other security events.

### Webhook URL

Set the Detec webhook URL to:

```
https://splunk-hec:8088/services/collector/event?token=YOUR_HEC_TOKEN
```

Alternatively, use an intermediary that receives Detec webhooks and forwards them to HEC with the token in the `Authorization` header.

### HEC JSON payload format

```json
{
  "event": {
    "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "event_type": "enforcement.applied",
    "observed_at": "2026-03-11T03:14:22Z",
    "tenant_id": "tenant-uuid",
    "endpoint": { "hostname": "prod-db-01", "posture": "active" },
    "tool": { "name": "Unknown Agent", "class": "C", "attribution_confidence": 0.82 },
    "policy": { "decision_state": "block", "rule_id": "ENFORCE-004" },
    "enforcement": {
      "tactic": "process_kill",
      "success": true,
      "pids_killed": [12345, 12346, 12347],
      "process_name": "python3",
      "cmdline_snippet": "python3 agent.py --target prod-db"
    },
    "severity": { "level": "S3" }
  },
  "sourcetype": "detec:enforcement",
  "source": "detec",
  "index": "main",
  "host": "prod-db-01"
}
```

### Sourcetype and index suggestions

| Field | Suggested value |
|---|---|
| `sourcetype` | `detec:enforcement` |
| `source` | `detec` |
| `index` | Your security events index (e.g. `security`, `main`) |
| `host` | `endpoint.hostname` from the payload |

## HMAC Verification

Always verify `X-Detec-Signature` before processing webhooks. The signature is computed over the raw request body (UTF-8 bytes) using HMAC-SHA256 with your webhook secret.

### Python example

```python
import hashlib
import hmac

def verify_detec_webhook(body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
```

### Verification flow

1. Receive the raw request body as bytes (do not parse JSON first; the signature is over the exact bytes).
2. Read the `X-Detec-Signature` header (format: `sha256=<hex>`).
3. Compute HMAC-SHA256 of the body using your webhook secret (from Detec dashboard, prefixed `whsec_`).
4. Compare the computed hex digest with the value after `sha256=` using a constant-time comparison (`hmac.compare_digest`).

**Security note:** Never log the webhook secret. Rotate secrets regularly.

## Retry Behavior

Detec retries failed deliveries to improve reliability:

| Setting | Value |
|---|---|
| Max retries | 3 |
| Backoff | Exponential: 1s, 4s, 16s |
| Timeout per attempt | 10 seconds |
| Success | HTTP 2xx |
| Retry | Any non-2xx status or connection error |

Use `X-Detec-Delivery-Id` for idempotency: if your endpoint returns 2xx, Detec considers the delivery successful and will not retry. If you process asynchronously, store the delivery ID and deduplicate before reprocessing.
