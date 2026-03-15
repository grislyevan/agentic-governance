# Detec Demo Proof — Project Specification

## Project name

detec-demo-proof

## Goal

Create a polished, repeatable demo artifact set for Detec so investors, design partners, and first-time technical reviewers can see a clean product story with concrete evidence.

## Background

Detec now has:

- a discovery-first README
- a one-minute demo flow
- a working `detec` CLI alias
- clean scan output with `validation failures: 0`

The next step is to turn that into a stable, presentation-ready demo package rather than relying on ad hoc local terminal output.

## Problem statement

The current demo flow works, but it still depends on whatever happens to exist on the operator's machine at run time.

That is fine for development, but not ideal for:

- investor walkthroughs
- design partner intros
- README screenshots
- repeatable product demos
- controlled technical evaluation

## Goal state

Detec should have a small, trustworthy demo proof set that gives a first-time viewer:

- a repeatable terminal demonstration
- a clean screenshot or transcript
- deterministic or near-deterministic example evidence
- output that matches the README story

## Requirements

1. Produce a stable demo artifact set for the recommended Detec scan flow.
2. The demo artifact set must include at least:
   - one clean terminal transcript or terminal-style output artifact
   - one screenshot or image of the successful demo flow, if feasible in-repo
   - one short demo evidence document describing what was run and what the viewer should notice
3. Align the artifact set with the README one-minute demo section.
4. Prefer deterministic or controlled demo evidence over highly variable live endpoint output.
5. If fixtures, sample outputs, or canned evidence are introduced, they must be clearly labeled as demo/sample evidence.
6. Preserve the truthful product story. Do not fake capabilities or hide real constraints.
7. Keep the project focused on demo proof only. Do not redesign the collector, policy system, dashboard, or API.
8. If a scripted demo path is added, it should be minimal and easy to understand.
9. Any added artifacts should be placed in repo-appropriate locations and named clearly.

## Acceptable approaches

Examples of acceptable implementations:

- checked-in sample terminal transcript generated from a validated run
- screenshot captured from a clean successful demo session
- minimal demo fixture or sample event path for a predictable README/demo experience
- a short demo script that runs the documented flow and emits stable evidence

## Unacceptable scope expansion

Do not:

- build a full interactive demo environment
- add major dashboard demo features
- add new detector capabilities unrelated to the demo
- create elaborate marketing content beyond the minimum useful artifact set
- rewrite existing architecture for the sake of a prettier demo

## Success criteria

1. A reviewer can open the repo and find a concrete demo evidence set quickly.
2. README demo claims are backed by visible artifacts in the repo.
3. The demo artifacts are clean enough to use in investor/design-partner conversations.
4. The artifacts are truthful and clearly labeled where they are sample-based.
5. The work remains minimal and scoped.

## Validation requirements

EvidenceQA and final integration must verify:

- demo artifacts exist
- artifacts are aligned with the README
- any scripted or fixture-based path is clearly documented
- demo evidence is readable, credible, and not misleading

## Suggested deliverables

1. Updated task list at `project-tasks/detec-demo-proof-tasklist.md`
2. Foundation/architecture guidance for demo artifacts
3. Demo evidence artifacts (transcript, screenshot, and/or sample output)
4. Short documentation describing the demo proof set
5. Completion report with final status and known limitations

## Out of scope

- new dashboard features
- policy engine changes
- broad collector refactors
- packaging/release work
- branding overhaul
- website/landing-page work
