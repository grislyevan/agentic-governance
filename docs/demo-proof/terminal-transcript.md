# Demo / sample evidence: one-minute scan transcript

This transcript is **sample demo evidence** that matches the output shape of the README one-minute demo. It was produced from a validated run of `pip install -e .` followed by `detec scan --verbose` (or `detec-agent scan --verbose`). On your machine, tool names and counts may differ; the important elements are: detected tools, confidence scores, and the final "Scan complete" line with events emitted and validation failures.

---

```
=== Scanning for Cursor ===
  Cursor: change detected (initial)
  Confidence: 0.7234 (High)
  Signals - P:0.85 F:0.90 N:0.70 I:0.65 B:0.00
  Emitting detection.observed event...

=== Scanning for Ollama ===
  Ollama: change detected (initial)
  Confidence: 0.8100 (High)
  Signals - P:0.95 F:0.80 N:0.90 I:0.00 B:0.00
  Emitting detection.observed event...

============================================================
Scan complete. Events emitted: 2, validation failures: 0
```
