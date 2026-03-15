# Demo proof: one-minute scan

This folder holds **stable demo evidence** for the Detec one-minute demo so investors, design partners, and first-time reviewers can see a clean product story with concrete artifacts. It backs the [README one-minute demo](../../README.md#one-minute-demo) without relying on whatever is on the operator's machine at run time.

## What was run

1. **Install** (from repo root): `pip install -e .`
2. **One-shot scan:** `detec scan --verbose` or `detec-agent scan --verbose`

No API or dashboard is required for this flow; the agent runs locally and prints detections to the console.

## What to notice

- **Detected tools:** Each scanner (Cursor, Ollama, Claude Code, etc.) reports whether it found evidence of that tool. The example shows Cursor and Ollama; your run may show different tools depending on what is installed and running.
- **Confidence:** Each detection has a score (e.g. 0.72, 0.81) and a band (e.g. High). The five dimensions (P, F, N, I, B) are documented in the playbook.
- **Scan complete:** The final line reports how many events were emitted and how many validation failures occurred. A clean run shows `validation failures: 0`.

## Artifacts in this folder

| Artifact | Description |
|----------|-------------|
| [terminal-transcript.md](terminal-transcript.md) | Sample terminal output from a validated one-minute run. Labeled as demo/sample evidence; shape matches the README example. |
| Screenshot | Optional. We do not capture an in-repo screenshot automatically (no terminal screenshot step in the pipeline). For live demos or README screenshots, run the commands above and capture the terminal manually. The transcript is the primary checked-in evidence. |

## Alignment with README

The root [README](../../README.md) one-minute demo section shows the same commands and the same output shape. This folder provides:

- A **repeatable reference:** The transcript and this doc are checked in so reviewers see evidence without running the scan themselves.
- **Truthful labeling:** The transcript is explicitly sample/demo evidence; we do not claim it is from your machine or that tool counts will match.

## Running it yourself

From the repo root:

```bash
pip install -e .
detec scan --verbose
```

Or use the long form: `detec-agent scan --verbose`. You should see scanner output and a final "Scan complete" line. For the full stack and dashboard demo, see [docs/demo.md](../demo.md) (five-minute demo).
