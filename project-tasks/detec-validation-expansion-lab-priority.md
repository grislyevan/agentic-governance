# Lab run priority for 20–30 tool coverage

**Workstream 1.** Prioritized list for which tools to add next so the project can reach 20–30 real tools tested.

## Current coverage (completed runs with RESULTS)

| Run ID | Tool | Calibration fixture |
|--------|------|---------------------|
| LAB-RUN-001/002 | Claude Code | LAB-RUN-001.json |
| LAB-RUN-003 | Ollama | LAB-RUN-003.json |
| LAB-RUN-004 | Cursor | LAB-RUN-004.json |
| LAB-RUN-005 | GitHub Copilot | LAB-RUN-005.json |
| LAB-RUN-006 | Open Interpreter | LAB-RUN-006.json |
| LAB-RUN-007 | OpenClaw | LAB-RUN-007.json |
| LAB-RUN-013 | OpenClaw (local LLM) | LAB-RUN-013.json |
| LAB-RUN-014 | Claude Cowork | LAB-RUN-014.json |

**Count:** 8 distinct tools with full RESULTS and fixtures. Evasion: LAB-RUN-EVASION-001 (Co-Authored-By).

## Priority 1: Complete live runs for template-only tools (5 tools)

These already have protocols and scanners; adding live runs and fixtures brings them to calibrated status.

| Order | Run ID | Tool | Protocol | Rationale |
|-------|--------|------|----------|-----------|
| 1 | LAB-RUN-008 | Aider | LAB-RUN-008-TEMPLATE-aider.md | Class C; high developer use |
| 2 | LAB-RUN-012 | Cline | LAB-RUN-012-TEMPLATE-cline.md | Class A/C; IDE-embedded |
| 3 | LAB-RUN-010 | Continue | LAB-RUN-010-TEMPLATE-continue.md | Class A/C; multi-LLM |
| 4 | LAB-RUN-009 | LM Studio | LAB-RUN-009-TEMPLATE-lm-studio.md | Class B; local models |
| 5 | LAB-RUN-011 | GPT-Pilot | LAB-RUN-011-TEMPLATE-gpt-pilot.md | Class C; autonomous |

**After Priority 1:** 8 + 5 = 13 tools with full RESULTS.

## Priority 2: Gap and variant scenarios (existing tools)

| Order | Scenario | Protocol / note | Rationale |
|-------|----------|-----------------|------------|
| 1 | LAB-RUN-015 | Claude Cowork gap (scheduled, DXT, skill-creator) | Protocol ready; completes Cowork coverage |
| 2 | LAB-RUN-001-root | Claude Code root rerun | Template exists; full visibility baseline |

**After Priority 2:** 13 + 2 = 15 scenarios (some same tool, different scenario).

## Priority 3: Additional tools from playbook / init-issues (to reach 20–30)

Playbook Section 4 and init-issues (INIT-13 through INIT-22) define detection profiles. Tools that have scanners but no live run yet are above. To reach 20–30 *tools* (not just scenarios), add live runs for net-new tools, for example:

- **MCP** (MCPScanner): multi-server, protocol-specific; high value for agent ecosystems.
- **AI Extensions** (AIExtensionScanner): generic IDE extensions; one run to calibrate.
- **Other tools** named in playbook but not yet in scanner list: add scanner if needed, then lab run.

Suggested next IDs: LAB-RUN-016 (MCP or next tool), LAB-RUN-017, … through LAB-RUN-030 as needed. Each new tool needs: protocol in lab-runs/, live run, RESULTS, calibration fixture in collector/tests/fixtures/lab_runs/, and index update in docs/lab-runs-and-results.md and playbook Section 12.5.

## Summary

| Phase | Action | Approx. new runs | Cumulative tools/scenarios |
|-------|--------|------------------|----------------------------|
| Priority 1 | Live runs for Aider, Cline, Continue, LM Studio, GPT-Pilot | 5 | 13 tools |
| Priority 2 | Cowork gap (015), Claude Code root (001-root) | 2 | 15 scenarios |
| Priority 3 | Net-new tools (MCP, AI Extensions, others) | 5–15 | 20–30 |

**Rationale for order:** Template-only tools already have protocols and scanners; completing them is the fastest path to higher count. Gap and variant runs deepen coverage. Net-new tools require protocol authoring and possibly new scanner work.
