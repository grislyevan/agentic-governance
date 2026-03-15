# Detec Signal Credibility — Project Specification

## Project name

detec-signal-credibility

## Goal

Improve the credibility of Detec scan results by reducing noisy, weak, or confusing detections so the output feels more intentional and trustworthy to security-minded users.

## Background

Detec now has:

- a clear README and demo flow
- a working short CLI alias
- clean schema-valid scan output with `validation failures: 0`

However, some detections may still feel low-signal or confusing in normal scans, especially cases where:

- the tool is not meaningfully present
- only a weak identity clue is available
- the output says little or no real signal was found, but still emits a detection/policy sequence
- confidence is extremely low but the event stream still looks busy

This can reduce trust, even when the schema is valid.

## Problem statement

A technically credible product should not only emit valid events; it should also make users feel that:

- detections are grounded
- weak evidence is handled intentionally
- low-confidence cases are not overstated
- the output reflects signal quality honestly

## Goal state

A normal scan should feel more trustworthy by:

- reducing confusing low-signal detections
- clarifying when something is merely a weak hint versus a real finding
- ensuring event emission and policy evaluation feel proportional to evidence quality

## Requirements

1. Identify scan outputs that are technically valid but weak, noisy, misleading, or trust-reducing.
2. Focus especially on cases where:
   - "no real signals detected" still results in a full detection event
   - confidence is extremely low
   - only generic environment/API-key evidence exists
   - extension-host or shared-process evidence creates ambiguous attribution
3. Improve credibility using minimal, targeted changes.
4. Preserve truthful reporting. Do not hide real findings just to make output look cleaner.
5. If thresholds, gating, or wording are changed, they must be justified and tested.
6. Maintain the current clean schema-valid output.
7. Do not add unrelated new detectors, dashboard work, or major architecture refactors.
8. Documentation should be updated only as needed to explain materially changed scan behavior.

## Credibility principles

The scan should communicate:

- strong detections clearly
- ambiguous detections carefully
- weak hints as weak hints
- non-detections as non-detections

It should avoid making the user think the product is inflating findings.

## Acceptable improvements

Examples:

- suppressing or downgrading emission for extremely weak non-actionable cases
- improving wording for weak-signal summaries
- tightening attribution thresholds for specific detectors
- separating "hint"/"artifact present" behavior from "detected tool" behavior if feasible within current design
- improving tests around weak-signal handling

## Unacceptable scope expansion

Do not:

- redesign the entire scoring model
- rebuild the policy engine
- create a new detection taxonomy unless absolutely necessary
- add new major product surfaces
- rewrite the collector broadly

## Success criteria

1. Normal scan output feels more credible to a technical reviewer.
2. Extremely weak or confusing detections are reduced, reclassified, or clarified.
3. Strong detections still appear correctly.
4. Schema-valid output remains intact.
5. Changes are minimal, justified, and tested.

## Validation requirements

EvidenceQA and final integration must verify:

- at least a few previously weak/noisy cases are improved
- strong detections are not regressed
- scan output remains schema-valid
- the resulting output is more readable and believable

Validation should include:

- before/after examples
- terminal output snippets where useful
- exact files changed
- rationale for any threshold or emission behavior change

## Suggested focus areas

Investigate only as needed:

- emission gating
- attribution confidence thresholds
- low-confidence policy/event behavior
- weak identity-only detections
- ambiguous extension-host detections
- summary wording for non-detections vs detections

## Deliverables

1. Updated task list at `project-tasks/detec-signal-credibility-tasklist.md`
2. Foundation/architecture guidance for credibility improvements
3. Implementation changes for targeted weak-signal handling
4. QA evidence with before/after examples
5. Completion report with final status and remaining limitations

## Out of scope

- dashboard features
- packaging/release work
- landing-page work
- broad repo cleanup
- major scoring-engine rewrite
