# DETEC-BEH-CORE-01 demo: Autonomous shell fan-out

**Detection name:** DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out  
**Why it matters:** Detects autonomous command execution that looks like an agent operating beyond normal interactive developer behavior.

Showable in 60 seconds: command, detection output, evidence summary, policy result.

---

## Command

From repo root, run the behavioral replay test that seeds a shell fan-out scenario (8 shells + LLM activity), then run the scanner:

```bash
cd /path/to/agentic-governance
pip install -e .
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'collector')
sys.path.insert(0, 'collector/tests')
from fixtures.behavioral_core_fixtures import seed_shell_fanout_positive
from scanner.behavioral import BehavioralScanner
from engine.confidence import compute_confidence, classify_confidence
from engine.policy import evaluate_policy
store = seed_shell_fanout_positive()
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

Or run the full test suite for DETEC-BEH-CORE-01 (positive, false-positive, ambiguous, renamed):

```bash
pytest collector/tests/test_behavioral_core_detections.py::TestDETEC_BEH_CORE_01_ShellFanout -v
```

---

## Detection output (captured)

```
DETECTED: Unknown Agent | confidence: 0.82 | band: High
detection_codes: ['DETEC-BEH-CORE-01', 'DETEC-BEH-CORE-03']
action_summary: Autonomous shell execution pattern detected: 8 shell children spawned from a model-linked parent process over 60 seconds. Sensitive access followed by outbound activity: /home/dev/.env accessed; outbound connections to api.anthropic.com within 5.0 seconds; destination type model.
policy: block ENFORCE-D01
```

*(This fixture also triggers DETEC-BEH-CORE-03 because it includes sensitive file + outbound for aggregate; in a 01-only scenario the summary would be the first sentence only.)*

---

## Evidence summary

- **Root process:** python3 (agent parent)
- **Shell children in window:** 8
- **Window:** 60 seconds
- **Model-linked:** true (LLM activity in same tree)
- **Sample commands:** `bash -c 'cmd-0'`, … `bash -c 'cmd-7'`

---

## Policy result

- **Decision state:** block (Class D persistent autonomous agent, R3 action)
- **Rule:** ENFORCE-D01
- **Reason codes:** class_d_tool, high_confidence, action_risk_r3, class_d_persistent_autonomous_agent, r3_or_higher_action_always_block_for_class_d

---

*Artifact for [behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md). Names and output are stable; run the commands above to reproduce.*
