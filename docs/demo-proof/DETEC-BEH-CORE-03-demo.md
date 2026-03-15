# DETEC-BEH-CORE-03 demo: Sensitive access followed by outbound

**Detection name:** DETEC-BEH-CORE-03 — Sensitive Access Followed by Outbound Activity  
**Why it matters:** Detects high-risk sequences where sensitive material is accessed and followed by outbound model or network activity.

Showable in 60 seconds: command, detection output, evidence summary, policy result.

---

## Command

From repo root, run the behavioral replay test that seeds a sensitive-access-then-outbound scenario, then run the scanner:

```bash
cd /path/to/agentic-governance
pip install -e .
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'collector')
sys.path.insert(0, 'collector/tests')
from fixtures.behavioral_core_fixtures import seed_credential_outbound_positive
from scanner.behavioral import BehavioralScanner
from engine.confidence import compute_confidence, classify_confidence
from engine.policy import evaluate_policy
store = seed_credential_outbound_positive()
scanner = BehavioralScanner(event_store=store)
scanner._thresholds['detection_threshold'] = 0.28
result = scanner.scan()
if result.detected:
    conf = compute_confidence(result)
    band = classify_confidence(conf)
    decision = evaluate_policy(confidence=conf, confidence_class=band, tool_class=result.tool_class or 'C', sensitivity='Tier1', action_risk=result.action_risk, is_containerized=False)
    print('DETECTED:', result.tool_name, '| confidence:', round(conf, 2), '| band:', band)
    print('detection_codes:', result.evidence_details.get('detection_codes'))
    print('action_summary:', result.action_summary)
    print('policy:', decision.decision_state, decision.rule_id)
"
```

Or run the full test suite for DETEC-BEH-CORE-03:

```bash
pytest collector/tests/test_behavioral_core_detections.py::TestDETEC_BEH_CORE_03_SensitiveOutbound -v
```

---

## Detection output (captured)

```
DETECTED: Unknown Agent | confidence: 0.82 | band: High
detection_codes: ['DETEC-BEH-CORE-01', 'DETEC-BEH-CORE-03']
action_summary: Autonomous shell execution pattern detected: 6 shell children spawned from a model-linked parent process over 60 seconds. Sensitive access followed by outbound activity: /home/dev/.env accessed; outbound connections to api.anthropic.com within 12.0 seconds; destination type model.
policy: block ENFORCE-D01
```

*(Fixture includes shell fan-out for aggregate; the 03-specific evidence is below.)*

---

## Evidence summary (DETEC-BEH-CORE-03)

- **Sensitive paths accessed:** /home/dev/.env, /home/dev/.aws/credentials
- **First access time:** (timestamp)
- **First network time:** (timestamp)
- **Interval:** 12.0 seconds between first access and first outbound
- **Outbound destinations:** api.anthropic.com
- **Destination type:** model (vs unknown)
- **Confidence reasons:** sensitive_access_then_outbound

---

## Policy result

- **Decision state:** block (Class D, R3 action)
- **Rule:** ENFORCE-D01
- **Reason codes:** class_d_tool, high_confidence, action_risk_r3, class_d_persistent_autonomous_agent

For unknown (non-model) outbound destinations, NET-001 or NET-002 can apply; see [behavioral-core-policy-mapping.md](../behavioral-core-policy-mapping.md).

---

*Artifact for [behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md). Names and output are stable; run the commands above to reproduce.*
