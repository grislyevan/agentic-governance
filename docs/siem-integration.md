# SIEM Integration Guide

Detec forwards events to SIEMs and SOC tools via webhooks. Use the built-in templates in Settings > Webhooks to create pre-configured integrations, or use the generic webhook for custom setups.

## Quick Start

1. Go to **Settings** > **Webhooks**
2. Click **Create from template**
3. Choose a SIEM (Splunk, Elastic, Sentinel, PagerDuty, or Slack)
4. Fill in the required config fields (host, token, etc.)
5. Click **Create webhook**

The webhook is created with recommended event types. You can edit it later to change events or pause delivery.

---

## Splunk HEC

Forward events to Splunk via HTTP Event Collector (HEC).

### Setup

1. In Splunk, go to **Settings** > **Data inputs** > **HTTP Event Collector**
2. Create a new HEC token with the desired index (e.g. `main` or `security`)
3. In Detec, use the **Splunk HEC** template
4. Enter:
   - **Splunk Host**: Your Splunk host (e.g. `splunk.example.com`)
   - **HEC Token**: The token from step 2
   - **Index** (optional): Override index (default from token)
   - **Source Type** (optional): Default `detec:event`

### Verify

1. Create the webhook and click **Test**
2. In Splunk, run: `index=main sourcetype=detec:event`
3. You should see the test event

### Payload Format

Detec sends the standard webhook payload. Splunk indexes it as JSON. Use `event_type`, `endpoint.hostname`, `tool.name`, and `policy.rule_id` for searches and dashboards.

---

## Elastic Security

Forward events to Elasticsearch or Elastic Cloud.

### Setup

1. In Kibana, go to **Management** > **API Keys**
2. Create an API key with `create_index` and `index` privileges for your index
3. In Detec, use the **Elastic Security** template
4. Enter:
   - **Elasticsearch Host**: Your cluster host (e.g. `my-cluster.es.io`)
   - **API Key**: The base64-encoded API key from step 2
   - **Index Name** (optional): Default `detec-events`

### Verify

1. Create the webhook and click **Test**
2. In Kibana, run: `GET detec-events/_search`
3. You should see the test document

### Index Mapping

For best results, create an index template or let Elastic dynamic mapping handle the payload. Key fields: `event_type`, `endpoint.hostname`, `tool.name`, `policy.decision_state`, `severity.level`.

---

## Microsoft Sentinel

Forward events to Microsoft Sentinel via the Log Analytics Data Collector API.

### Setup

1. In Azure Portal, open your Log Analytics workspace
2. Go to **Agents** > **Log Analytics agent instructions**
3. Copy the **Workspace ID** and **Primary Key**
4. In Detec, use the **Microsoft Sentinel** template
5. Enter:
   - **Workspace ID**: From step 3
   - **Primary Key**: From step 3
   - **Log Type** (optional): Default `DetecEvent`

### Verify

1. Create the webhook and click **Test**
2. In Sentinel, go to **Logs** and run: `DetecEvent_CL | take 10`
3. Events may take a few minutes to appear

### Note

The Log Analytics Data Collector API requires request signing with the shared key. The template creates the webhook with the correct URL. For full integration, ensure your setup supports the Data Collector API format. See the [Data Collector API docs](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-collector-api) for details.

---

## PagerDuty

Trigger incidents in PagerDuty for enforcement events.

### Setup

1. In PagerDuty, create a service or use an existing one
2. Add an **Events API v2** integration and copy the **Integration Key**
3. In Detec, use the **PagerDuty** template
4. Enter:
   - **Integration Key**: The routing key from step 2
   - **Default Severity** (optional): `warning`, `error`, or `critical`

### Verify

1. Create the webhook and click **Test**
2. A test incident should appear in PagerDuty

### Event Types

The template subscribes to `enforcement.block`, `enforcement.applied`, `enforcement.escalated`, and `enforcement.failed`. Adjust in the webhook settings if needed.

---

## Slack

Post event notifications to a Slack channel.

### Setup

1. In Slack, go to **Apps** > **Incoming Webhooks** (or create a Slack app with incoming webhook)
2. Add a webhook to your workspace and copy the webhook URL
3. In Detec, use the **Slack** template
4. Enter:
   - **Webhook URL**: The URL from step 2
   - **Channel Override** (optional): Override the default channel (e.g. `#security-alerts`)

### Verify

1. Create the webhook and click **Test**
2. A message should appear in the configured channel

### Event Types

The template subscribes to `enforcement.block`, `enforcement.applied`, `enforcement.simulated`, and `enforcement.escalated`. Adjust as needed.

---

## Generic Webhook

For SIEMs or tools not covered by templates (e.g. IBM QRadar, Chronicle, custom receivers):

1. Click **Add webhook** (not "Create from template")
2. Enter the full webhook URL
3. Select event types or leave empty for all events

### HMAC Verification

All webhooks include:

- `X-Detec-Signature`: HMAC-SHA256 of the body with your webhook secret
- `X-Detec-Delivery-Id`: Unique ID for idempotency

Verify the signature before processing:

```python
import hashlib
import hmac

def verify_detec_webhook(body: bytes, signature_header: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
```

See [webhook-recipes.md](webhook-recipes.md) for more examples.

---

## Retry Behavior

| Setting   | Value                          |
|-----------|--------------------------------|
| Max retries | 3                            |
| Backoff   | Exponential: 1s, 4s, 16s       |
| Timeout   | 10 seconds per attempt        |
| Success   | HTTP 2xx                      |
| Retry     | Any non-2xx or connection error |

Use `X-Detec-Delivery-Id` for idempotency. If your endpoint returns 2xx, Detec considers the delivery successful and will not retry.
