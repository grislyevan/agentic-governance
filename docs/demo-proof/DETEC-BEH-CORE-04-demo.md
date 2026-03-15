# DETEC-BEH-CORE-04 demo: Agent execution chain

**Detection name:** DETEC-BEH-CORE-04 — Agent Execution Chain  
**Why it matters:** Detects the full agent loop: model call, then command execution, then file or git change, in order within a time window.

Showable in 60 seconds: command, detection output, evidence summary, policy result.

---

## Command

From repo root, run the behavioral replay that seeds an execution-chain scenario (LLM then shell then file write), then run the scanner:

```bash
cd /path/to/agentic-governance
pip install -e .
python -c "
import sys
sys.path.insert(0, 'collector')
sys.path.insert(0, 'collector/tests')
from fixtures.behavioral_core_fixtures import seed_execution_chain_positive
from scanner.behavioral import BehavioralScanner
from engine.confidence import compute_confidence, classify_confidence
from engine.policy import evaluate_policy
store = seed_execution_chain_positive()
scanner = BehavioralScanner(event_store=store)
scanner._thresholds['detection_threshold'] = 0.05
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

Or run the full test suite for DETEC-BEH-CORE-04 (BEH-009):

```bash
pytest collector/tests/test_behavioral_scanner.py::TestBEH009AgentExecutionChain -v
pytest collector/tests/test_behavioral_scanner.py -k "beh009 or detection_code" -v
```

---

## Detection output (captured)

```
DETECTED: Unknown Agent | confidence: 0.52 | band: Medium
detection_codes: ['DETEC-BEH-CORE-04']
action_summary: AI-driven command execution chain detected: LLM API call: api.anthropic.com:443; shell execution: bash; file write detected in 10.0 seconds.
policy: warn ENFORCE-002
```

---

## Evidence summary

- **Sequence:** LLM API call (api.anthropic.com:443), then shell execution (bash), then file write
- **Window:** 10 seconds from first LLM event to file event
- **Layers:** network, process, file (all three required in order)

---

## Policy result

- **Decision state:** warn (or block/approval_required depending on posture and sensitivity)
- **Rule:** ENFORCE-002 or ISO-001
- **Reason:** Medium confidence, Class C tool, action risk from pattern mix

---

*Artifact for [behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md). Names and output are stable; run the commands above to reproduce.*
