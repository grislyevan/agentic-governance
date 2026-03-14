# Example: One block decision and why

This document walks through one concrete block so you can see what happened, which rule fired, and why. The same event chain is in [sample-events.json](sample-events.json).

## Scenario

Claude Code (an autonomous coding agent) attempted a privileged operation and repo mutation on a crown-jewel asset. The endpoint was classified as Tier3 (crown-jewel). Detec detected the tool, evaluated policy, and blocked the action.

## Event (snippet)

From the detection and policy evaluation:

| Field | Value |
|-------|--------|
| **Tool** | Claude Code |
| **Class** | C (Autonomous Executor) |
| **Action type** | privileged |
| **Risk class** | R4 (privileged/destructive/prohibited) |
| **Target sensitivity** | Tier3 (crown-jewel) |
| **Attribution confidence** | 0.88 |

Summary: "Claude Code attempted privileged operation and repo mutation on crown-jewel asset."

## Rule

**ENFORCE-005** (from baseline policies):

- **Description:** Explicit deny on crown-jewel or regulated assets. Blocks regardless of confidence level.
- **Conditions:** confidence_band any (Low, Medium, High); tool_classes A, B, C; sensitivity_tiers Tier3; explicit_deny True.
- **Decision state:** block.
- **Precedence:** 500 (takes effect over lower-precedence rules).

## Decision

**Block.** The policy engine matched ENFORCE-005 because the target was Tier3 and the rule is an explicit deny for crown-jewel assets. No other rule overrides it at higher precedence.

## Why

1. The tool is Class C (autonomous executor): it can run shell, write files, and mutate repos.
2. The action was classified R4 (privileged/destructive/prohibited).
3. The target endpoint/asset is Tier3 (crown-jewel). ENFORCE-005 says: on Tier3, block regardless of confidence.
4. Therefore the engine returned decision_state **block** with rule_id **ENFORCE-005**.

Enforcement: the agent (or server-directed enforcement) applied **process_kill**. Detail: "Killed PID [3901] for claude process performing git write in protected repo." The outcome is **denied**.

## Evidence chain

- **Process layer:** Claude process and child chain identified.
- **File layer:** Config and session artifacts under `~/.claude/` and repo context.
- **Attribution confidence 0.88** (High band): multiple layers aligned, so the block threshold is met and ENFORCE-005 applies.

## Tie-in

The same three-event chain (detection → policy.evaluated → enforcement.applied) is in [sample-events.json](sample-events.json) with event_ids `demo-detect-001`, `demo-policy-001`, and `demo-enforce-001`. You can use that file to see the full canonical payload shape or to test integrations.
