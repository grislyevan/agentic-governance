# DETEC-BEH-CORE-02 demo: Agentic read-modify-write loop

**Detection name:** DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop  
**Why it matters:** Detects AI-assisted code modification loops, not just AI tool presence.

Showable in 60 seconds: command, detection output, evidence summary, policy result.

---

## Command

From repo root, run the behavioral replay test that seeds an RMW scenario (file–model–file cycles), then run the scanner:

```bash
cd /path/to/agentic-governance
pip install -e .
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'collector')
sys.path.insert(0, 'collector/tests')
from fixtures.behavioral_core_fixtures import seed_rmw_positive
from scanner.behavioral import BehavioralScanner
from engine.confidence import compute_confidence, classify_confidence
from engine.policy import evaluate_policy
store = seed_rmw_positive()
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

Or run the full test suite for DETEC-BEH-CORE-02:

```bash
pytest collector/tests/test_behavioral_core_detections.py::TestDETEC_BEH_CORE_02_RMWLoop -v
```

---

## Detection output (captured)

```
DETECTED: Unknown Agent | confidence: 0.54 | band: Medium
detection_codes: ['DETEC-BEH-CORE-02', 'DETEC-BEH-CORE-03']
action_summary: Agentic read-modify-write loop detected: 3 file-model cycles in 10 seconds affecting /home/dev, /proj/d0, /proj/d1, tied to process cursor (api.anthropic.com). Sensitive access followed by outbound activity: /home/dev/.env accessed; outbound connections to api.anthropic.com within 5.0 seconds; destination type model.
policy: block ISO-001
```

*(Fixture includes both RMW and sensitive+outbound; 02-only scenario would show the first sentence only.)*

---

## Evidence summary

- **Cycles detected:** 3 file–model–file cycles
- **Cycle window:** 10 seconds
- **Model endpoint:** api.anthropic.com
- **Affected directories:** /home/dev, /proj/d0, /proj/d1, /proj/d2, /proj/lib, /proj/src
- **Affected files:** /proj/src/a.py, /proj/lib/b.py, /proj/src/c.py, and others in burst

---

## Policy result

- **Decision state:** block
- **Rule:** ISO-001 (or ENFORCE-* depending on posture and sensitivity)
- **Reason:** Medium confidence, Class C/D tool, action risk R3

---

*Artifact for [behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md). Names and output are stable; run the commands above to reproduce.*
