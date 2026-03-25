# Demo Proof Index

This directory contains demo proof artifacts: detection outputs, event traces, and session reports generated from behavioral core demo runs. Artifacts here are generated from the test harness and represent representative detection outputs. They are not live captures.

---

## Artifact Index

| File | Detection | Purpose |
|------|-----------|---------|
| [DETEC-BEH-CORE-01-demo.md](DETEC-BEH-CORE-01-demo.md) | Autonomous Shell Fan-Out | Detection output, event trace, evidence summary |
| [DETEC-BEH-CORE-02-demo.md](DETEC-BEH-CORE-02-demo.md) | Agentic Read-Modify-Write Loop | Detection output, event trace, evidence summary |
| [DETEC-BEH-CORE-03-demo.md](DETEC-BEH-CORE-03-demo.md) | Sensitive Access Followed by Outbound Activity | Detection output, event trace, evidence summary |
| [DETEC-BEH-CORE-04-demo.md](DETEC-BEH-CORE-04-demo.md) | Agent Execution Chain | Detection output, event trace, evidence summary |
| [session-report-demo.md](session-report-demo.md) | All / session aggregation | Session report output: tool, duration, action counts, risk signals |

---

## Note on Artifact Origin

Artifacts in this directory are generated from test harness runs and represent representative detection outputs. They are not live captures.

The behavioral demo pack ([docs/behavioral-core-demo-pack.md](../behavioral-core-demo-pack.md)) describes what each detection triggers on, trigger conditions, and policy defaults.

---

## How to Regenerate

```bash
make bootstrap-dev && python -m pytest collector/tests/test_behavioral_core_detections.py -v
```

To run a single detection:

```bash
python -m pytest collector/tests/test_behavioral_core_detections.py -k "DETEC_BEH_CORE_01" -v
```

To view the full detection output including event traces, run the collector with verbose output:

```bash
detec scan --verbose
```
