# DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity (Implementation Spec)

## Intent

Detect access to sensitive paths (e.g. .env, .ssh, .aws, credentials, kube config) followed by outbound network activity (model provider or unknown destination). Strongest buyer-facing story; maps to data exfiltration and unauthorized access concerns.

## Internal pattern

BEH-006 (Config/credential access) in `collector/scanner/behavioral_patterns.py`, hardened with temporal ordering and destination classification.

## Trigger conditions

- At least one sensitive path access (file event to a path matching sensitive fragments).
- Outbound network activity occurs *after* the first sensitive access within a configurable time window (temporal ordering).
- Same process tree (or correlated) performs both access and network.
- Confidence increases when destination is unknown (not on model-provider allowlist) or repeated.

## Telemetry required

- File events: path, action, timestamp, pid (for sensitive path matching).
- Network events: remote_addr, sni, timestamp, pid.
- Process tree for correlation.

## Thresholds (explicit)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `credential_access_min_files` | 1 | Minimum sensitive file events. |
| `credential_require_network` | true | Require at least one outbound connection. |
| `credential_network_max_seconds_after_access` | 300 | Max seconds between first sensitive access and first qualifying network (temporal ordering). |

Sensitive path fragments: `.env`, `/.ssh/`, `/.aws/`, `/.config/gcloud`, `/.azure/`, `credentials`, `secrets`, `.netrc`, `.npmrc`, `keychain`, `/.kube/` (kube config).

## Confidence and penalties

- Confidence: BEH-006 score; boost when destination is unknown (not LLM host) or multiple distinct outbound. Current scoring: 1+ file + network 0.6; 3+ files 0.7; 5+ files + network 1.0.
- Penalties: none specific to BEH-006; general behavioral penalties apply.

## Evidence output (schema)

- `sensitive_files_accessed`: count
- `paths`: list of sensitive paths touched (e.g. first 10)
- `has_network`: boolean
- `first_access_time`, `first_network_time`, `interval_seconds`: for temporal ordering
- `outbound_destinations`: list of host:port or sni
- `model_vs_unknown`: classification (e.g. "model", "unknown", "both")
- `confidence_reasons`: e.g. "sensitive_access_then_unknown_outbound"

## Sample event output

```json
{
  "behavioral_patterns": [{
    "pattern_id": "BEH-006",
    "pattern_name": "Config/credential access",
    "score": 0.8,
    "evidence": {
      "sensitive_files_accessed": 2,
      "paths": ["/home/dev/.env", "/home/dev/.aws/credentials"],
      "has_network": true,
      "interval_seconds": 12,
      "outbound_destinations": ["api.anthropic.com:443"],
      "model_vs_unknown": "model",
      "confidence_reasons": ["sensitive_access_then_outbound"]
    }
  }],
  "root_process": { "pid": 9012, "name": "python", "cmdline": "python agent.py" }
}
```

## Expected false positives

- Legitimate use: developer loads .env then runs app that calls API. Mitigation: temporal window and optional requirement that destination be unknown to focus on higher-risk exfiltration; model-only after .env may still trigger but policy can be warn/approval_required rather than block.
- SSH/config read by IDE or git. Mitigation: single read with no subsequent outbound does not trigger (credential_require_network + temporal ordering).

## Analyst summary (target)

"Sensitive access followed by outbound activity: path X accessed; outbound connections to [destinations] within N seconds; [model/unknown]."
