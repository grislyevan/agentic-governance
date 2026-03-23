---
name: New evasion report
description: Report a newly discovered evasion or bypass so we can add detection and a scenario
title: "[Evasion] "
labels: ["evasion", "INIT-31"]
---

## Summary

(One or two sentences: what bypass or evasion was observed, and under what conditions.)

## Evasion class (if known)

- [ ] E1 (binary/global hook)
- [ ] E2 (template/repo hook, container)
- [ ] E3 (force-push / history rewrite)
- [ ] E4 (renamed binary, CoAuthoredBy)
- [ ] E5 (Cursor git/telemetry disabled)
- [ ] E6 (agent disable/kill loop)
- [ ] E7 (config tamper / policy suppression)
- [ ] E8 (telemetry shaping / provider downgrade)
- [ ] Other / new class

## Steps or environment

(How to reproduce: OS, tool version, config, or steps that lead to the bypass.)

## Expected vs actual

- **Expected:** Detector should flag this (or policy should elevate response).
- **Actual:** No finding, or wrong severity.

## Proposed scenario (optional)

If you have a concrete scenario (tool, vector, expected outcome), describe it so we can add it to `evasion_suite_scenarios.py` and the runtime suite.

## Environment

- OS:
- Collector/API version or commit:
