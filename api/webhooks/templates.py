"""Pre-built webhook templates for common SIEM/SOC integrations."""

SIEM_TEMPLATES = [
    {
        "id": "splunk_hec",
        "name": "Splunk HEC",
        "description": "Forward events to Splunk via HTTP Event Collector",
        "url_pattern": "https://{splunk_host}:8088/services/collector/event",
        "headers": {"Authorization": "Splunk {hec_token}"},
        "payload_transform": "splunk_hec",
        "docs_url": "https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector",
        "config_fields": [
            {"key": "splunk_host", "label": "Splunk Host", "placeholder": "splunk.example.com", "required": True},
            {"key": "hec_token", "label": "HEC Token", "placeholder": "your-hec-token", "required": True, "secret": True},
            {"key": "index", "label": "Index", "placeholder": "main", "required": False},
            {"key": "sourcetype", "label": "Source Type", "default": "detec:event", "required": False},
        ],
    },
    {
        "id": "elastic",
        "name": "Elastic Security",
        "description": "Forward events to Elasticsearch or Elastic Cloud",
        "url_pattern": "https://{elastic_host}:9200/{index_name}/_doc",
        "headers": {"Authorization": "ApiKey {api_key}"},
        "payload_transform": "elastic",
        "docs_url": "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-index_.html",
        "config_fields": [
            {"key": "elastic_host", "label": "Elasticsearch Host", "placeholder": "my-cluster.es.io", "required": True},
            {"key": "api_key", "label": "API Key", "placeholder": "base64-encoded-api-key", "required": True, "secret": True},
            {"key": "index_name", "label": "Index Name", "default": "detec-events", "required": False},
        ],
    },
    {
        "id": "sentinel",
        "name": "Microsoft Sentinel",
        "description": "Forward events to Microsoft Sentinel via Log Analytics Data Collector API",
        "url_pattern": "https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01",
        "headers": {},
        "payload_transform": "sentinel",
        "docs_url": "https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-collector-api",
        "config_fields": [
            {"key": "workspace_id", "label": "Workspace ID", "placeholder": "your-workspace-id", "required": True},
            {"key": "shared_key", "label": "Primary Key", "placeholder": "your-shared-key", "required": True, "secret": True},
            {"key": "log_type", "label": "Log Type", "default": "DetecEvent", "required": False},
        ],
    },
    {
        "id": "pagerduty",
        "name": "PagerDuty",
        "description": "Trigger incidents in PagerDuty for enforcement events",
        "url_pattern": "https://events.pagerduty.com/v2/enqueue",
        "headers": {},
        "payload_transform": "pagerduty",
        "docs_url": "https://developer.pagerduty.com/docs/events-api-v2/trigger-events/",
        "config_fields": [
            {"key": "routing_key", "label": "Integration Key", "placeholder": "your-routing-key", "required": True, "secret": True},
            {"key": "severity", "label": "Default Severity", "default": "warning", "required": False},
        ],
    },
    {
        "id": "slack",
        "name": "Slack",
        "description": "Post event notifications to a Slack channel",
        "url_pattern": "{webhook_url}",
        "headers": {},
        "payload_transform": "slack",
        "docs_url": "https://api.slack.com/messaging/webhooks",
        "config_fields": [
            {"key": "webhook_url", "label": "Webhook URL", "placeholder": "https://hooks.slack.com/services/...", "required": True, "secret": True},
            {"key": "channel", "label": "Channel Override", "placeholder": "#security-alerts", "required": False},
        ],
    },
]


def get_templates():
    return SIEM_TEMPLATES


def get_template(template_id: str):
    for t in SIEM_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def _apply_defaults(template: dict, config: dict) -> dict:
    """Merge template config_field defaults into config for URL/header building."""
    merged = dict(config)
    for field in template.get("config_fields", []):
        key = field.get("key")
        if key and key not in merged and field.get("default"):
            merged[key] = field["default"]
    return merged


def build_url_from_template(template_id: str, config: dict) -> str:
    """Build the webhook URL from a template and config values."""
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")
    config = _apply_defaults(template, config)
    url = template["url_pattern"]
    for key, value in config.items():
        if value is not None and value != "":
            url = url.replace("{" + key + "}", str(value))
    return url


def build_headers_from_template(template_id: str, config: dict) -> dict[str, str]:
    """Build headers from a template and config values. Returns empty dict if no headers."""
    template = get_template(template_id)
    if not template or not template.get("headers"):
        return {}
    config = _apply_defaults(template, config)
    result = {}
    for hk, hv in template["headers"].items():
        for key, value in config.items():
            if value is not None and value != "":
                hv = hv.replace("{" + key + "}", str(value))
        result[hk] = hv
    return result


def get_recommended_events(template_id: str) -> list[str]:
    """Return recommended event types for a template. SIEMs get all enforcement events; PagerDuty/Slack get critical ones."""
    if template_id in ("splunk_hec", "elastic", "sentinel"):
        return [
            "enforcement.block",
            "enforcement.approval_required",
            "enforcement.warn",
            "enforcement.allow",
            "enforcement.applied",
            "enforcement.simulated",
            "enforcement.escalated",
            "enforcement.failed",
            "tool.detected",
            "tool.removed",
        ]
    if template_id == "pagerduty":
        return [
            "enforcement.block",
            "enforcement.applied",
            "enforcement.escalated",
            "enforcement.failed",
        ]
    if template_id == "slack":
        return [
            "enforcement.block",
            "enforcement.applied",
            "enforcement.simulated",
            "enforcement.escalated",
        ]
    return []
