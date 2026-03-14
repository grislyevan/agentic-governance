# Detec Demo Readiness — Technical / UX Foundation

For implementers. Source: [project-specs/detec-demo-readiness-setup.md](../project-specs/detec-demo-readiness-setup.md) and [task list](../project-tasks/detec-demo-readiness-tasklist.md).

---

## 1. README structure

### 1.1 Order of sections

- **Line 1:** Main title: `# Detec (agentic-governance)` (unchanged).
- **Next:** Tagline: `**Discover and control autonomous AI tools on developer endpoints.**` (unchanged unless Task 3 adjusts it).
- **Optional (Task 3):** If discovery-first narrative is in scope, the opening sentence or short paragraph leads with "discover what AI tools run on developer machines"; governance/control is the next step.
- **Required:** A single **one-minute demo** section (new). It must be the first substantive section a reader sees, and must appear **before** the heading `## Repo layout` and before any other structural sections (e.g. "Get started", "Repo layout").
- **After the demo:** Existing content may follow (e.g. the current intro paragraph and bullet list, then `---`, then `## Repo layout`, then "Get started", etc.). The demo block may be an H2 such as `## One-minute demo` or `## Try it in one minute`.

### 1.2 One-minute demo section: required content

The demo section must contain exactly:

1. **2–3 line description:** What Detec does in one sentence (discover AI tools on developer machines). No em dashes; use commas, colons, or periods.
2. **Install command:** One of:
   - From repo: `pip install -e .`
   - When published: `pip install detec` (optional to mention).
3. **One-shot scan command:** Either:
   - `detec-agent scan --verbose` (always valid), or
   - `detec scan` (if the short CLI is implemented), with optional note that `detec-agent scan --verbose` also works.
4. **Example output:** A screenshot or pasted terminal output that shows:
   - At least one detected tool (e.g. Cursor, Claude Code, Ollama).
   - Capabilities or confidence (e.g. confidence score, capability labels).
   - The line "Scan complete" (or equivalent as emitted by the collector).

Use a fenced code block for the example output so it is readable and copy-paste safe.

### 1.3 What not to add

- No new folders (e.g. no `css/`). No changes to API, dashboard, or deploy behavior. Only README and optional CLI entry point.

---

## 2. Optional short `detec` CLI contract

If Task 2 is implemented:

- **Entry point name:** `detec` (single console script).
- **Behavior:** Thin wrapper that delegates to the existing `detec-agent` CLI. No new collector logic.
- **Subcommands:** At least `detec scan`; optionally `detec run`, `detec status`. Each must invoke `detec-agent <subcommand>` with the same arguments.
- **Implementation options:**
  - **Option A:** Add a second entry point in `pyproject.toml`, e.g. `detec = "collector.agent_cli:main"`, and inside `collector/agent_cli.py` detect `argv[0]` (e.g. `detec` vs `detec-agent`) and behave identically (same parser, same commands). No delegation process; same `main()`, so `detec scan` and `detec-agent scan` are one implementation.
  - **Option B:** New module that invokes `subprocess.run(["detec-agent", ...])` with `sys.argv[1:]`. Simpler but spawns a process; Option A is preferred for a single process.
- **Contract:** After `pip install -e .`, both `detec scan` and `detec-agent scan` must produce the same one-shot scan output; same for `run` and `status` if implemented.

---

## 3. Validation (for QA)

- **README:** Grep or read README and confirm the one-minute demo section exists and appears before the line `## Repo layout`. Confirm all four content elements (description, install, scan command, example output) are present.
- **CLI:** From repo root, run `pip install -e .` then `detec-agent scan --verbose` and, if implemented, `detec scan --verbose`; confirm output includes detected tools, confidence/capabilities, and "Scan complete".
- **No regressions:** No changes to scanner/confidence logic, API, or dashboard; only README and optional CLI.
