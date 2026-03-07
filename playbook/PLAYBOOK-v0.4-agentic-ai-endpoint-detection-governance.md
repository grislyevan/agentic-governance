# Agentic AI Endpoint Detection & Governance Playbook

**Version:** 0.4 — Rule ID Catalog + Enforcement Pipeline + Weight Alignment  
**Status:** Working Draft  
**Source Issues:** INIT-13–27, INIT-38, INIT-39, INIT-43  
**Shelved (pending running system):** INIT-28–37, INIT-40–42  

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Architecture Overview](#2-architecture-overview)
3. [Five-Layer Detection Model](#3-five-layer-detection-model)
4. [Tool Detection Profiles and Concrete IOCs](#4-tool-detection-profiles-and-concrete-iocs)
5. [Tool Class Policy Model](#5-tool-class-policy-model)
6. [Enforcement Ladder](#6-enforcement-ladder)
7. [Risky Action Controls](#7-risky-action-controls)
8. [Severity Taxonomy](#8-severity-taxonomy)
9. [Audit Schema and Event Model](#9-audit-schema-and-event-model)
10. [Exception Workflow](#10-exception-workflow)
11. [Tooling and Integration Map](#11-tooling-and-integration-map)
12. [Lab Validation Runs](#12-lab-validation-runs)
13. [Shelved Work Items](#13-shelved-work-items)
14. [Appendix A — Cross-Layer Correlation Rules](#appendix-a--cross-layer-correlation-rules)
15. [Appendix B — Confidence Scoring Reference](#appendix-b--confidence-scoring-reference)

---

## 1. Purpose and Scope

This playbook is the operational framework for detecting and governing agentic AI tools on enterprise endpoints. It consolidates detection profiles, policy models, enforcement logic, severity handling, audit schemas, and exception workflows into a single reference that engineering, security operations, and customer-facing teams can execute against.

### Design Principles

1. **Multi-signal attribution** — no single telemetry layer drives hard enforcement alone.
2. **Class-based governance** — policy targets capability and risk surface, not product names.
3. **Confidence-scored decisions** — every enforcement action carries an explainable confidence score.
4. **Progressive friction** — low-risk events get low-friction handling; high-risk events escalate fast.
5. **Audit-grade evidence** — every decision is traceable to immutable evidence objects.

### What This Document Covers

| In Scope (Active) | Shelved (Pending Running System) |
|---|---|
| Detection profiles: 11 tools (INIT-13–22 + OpenClaw) | Test matrix definition (INIT-28) |
| Policy class model (INIT-23) | Automated replay (INIT-29) |
| Enforcement ladder (INIT-24) | Metrics pipeline (INIT-30) |
| Risky action controls (INIT-25) | Evasion suite (INIT-31) |
| Audit schema (INIT-26) | Benchmark report generator (INIT-32) |
| Exception workflow (INIT-27) | Capability brief / positioning (INIT-33–37) |
| Severity taxonomy (INIT-38) | Tactics mapping (INIT-40) |
| Canonical event schema (INIT-39) | Privacy/legal review (INIT-41) |
| Signal map deep-dive (INIT-43) | Detection content update process (INIT-42) |

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      ENDPOINT TELEMETRY                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ Process  │ │  File/   │ │ Network  │ │ Identity │ │Behavior││
│  │ Lineage  │ │ Artifact │ │ Metadata │ │ /Access  │ │Sequence││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘│
└───────┼────────────┼────────────┼────────────┼─────────────┼─────┘
        └────────────┴────────────┴────────────┴─────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   ATTRIBUTION ENGINE        │
                    │  Multi-signal correlation   │
                    │  Tool class assignment       │
                    │  Confidence scoring          │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   POLICY ENGINE             │
                    │  Class → Controls mapping   │
                    │  Enforcement ladder eval    │
                    │  Exception resolution       │
                    └─────────────┬──────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                    │
    ┌─────────▼──────┐ ┌────────▼────────┐ ┌────────▼────────┐
    │  Enforcement    │ │  Audit/Evidence │ │  Severity &     │
    │  Actions        │ │  Pipeline       │ │  Incident Route │
    │  Detect→Block   │ │  Immutable logs │ │  S0–S4 triage   │
    └────────────────┘ └─────────────────┘ └─────────────────┘
```

**Data flow:** Raw telemetry from five layers feeds the attribution engine, which scores confidence and assigns tool classes. The policy engine evaluates enforcement using the class-based policy matrix, risky-action controls, and exception state. Outputs flow to enforcement actions, the audit pipeline, and severity-based incident routing.

---

## 3. Five-Layer Detection Model

Every tool profile in this playbook is structured around the same five telemetry layers. This consistency enables cross-tool comparison, unified confidence scoring, and class-based policy application.

### Layer Definitions

| Layer | What It Captures | Primary Value | Standalone Confidence |
|---|---|---|---|
| **A. Process / Execution** | Binary identity, parent-child lineage, session shape, command chains | Execution truth — strongest attribution anchor | Medium–High |
| **B. File / Artifact** | Config files, session caches, model storage, repo mutation patterns | Persistence and forensic continuity | Medium |
| **C. Network** | Destination endpoints, burst cadence, process-to-connection linkage | Cloud interaction corroboration | Low–Medium |
| **D. Identity / Access** | User/account mapping, endpoint posture, credential context | Governance enforceability (who, where, authorized?) | Medium |
| **E. Behavior** | Temporal action sequences, prompt-edit-commit loops, fan-out patterns | Agentic activity classification | Medium–High |

### Cross-Layer Correlation Requirement

Hard enforcement (Approval Required / Block) requires **minimum two aligned layers** with at least one being Process or Behavior. Single-layer signals drive Detect-only telemetry enrichment.

---

## 4. Tool Detection Profiles and Concrete IOCs

This section provides the concrete, operationalizable indicators of compromise (IOCs) for each in-scope tool, organized by detection layer. Each tool also carries a risk class assignment and governance posture.

---

### 4.1 Claude Code (INIT-13, INIT-43)

**Class:** C (Autonomous Executor) when shell/tool execution is active; A (Assistive) in chat-only mode  
**Risk Posture:** High in agentic mode  
**Lab Validated:** LAB-RUN-001 (2026-02-26, v2.1.59, macOS ARM64)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | CLI binary invocation (`claude` entrypoint, symlink to `cli.js`) from terminal parent. Parent chain: terminal → shell → claude. | High | ✓ Confirmed |
| **Process** | Child process chain: claude → shell → git/node/python subprocesses. Note: child processes are transient (sub-second lifetime); requires ESF or <1s polling to capture directly. Artifact-based confirmation (`.pytest_cache/`, `.pyc` files) is acceptable fallback. | High | ✓ Confirmed (indirect) |
| **Process** | Long-lived interactive sessions with iterative command bursts. Memory footprint grows during agentic activity (observed: 59 MB idle → 84 MB active). | Medium | ✓ Confirmed |
| **File** | `~/.claude/` global config/state directory. Created on **first launch** (not during install). Contains: `backups/`, `cache/`, `debug/`, `plugins/`, `todos/`, `plans/`, `projects/`, `session-env/`, `shell-snapshots/`, `file-history/`. Observed: 308 files after single session. Absence after install does not indicate absence of tool. | High | ✓ Confirmed |
| **File** | Session history/cache artifacts with recent timestamps. Session JSONL at `.claude/projects/-<path-hash>/<session-uuid>.jsonl`. Debug log at `.claude/debug/<session-uuid>.txt`. File-history artifacts with content hashes. | Medium–High | ✓ Confirmed |
| **File** | Plugin marketplace auto-clone on first launch. Git clone of `anthropics/claude-plugins-official` into `~/.claude/plugins/marketplaces/`. 200+ files including `.git/` — large, distinctive footprint. | Medium–High | ✓ Confirmed (new) |
| **File** | Feature flag cache in session config (`cachedGrowthBookFeatures`) with Anthropic-internal codenames (`tengu_*`). Useful for version fingerprinting and behavior prediction. | Low–Medium | ✓ Confirmed (new) |
| **File** | macOS Terminal preferences modification. Backs up `com.apple.Terminal.plist` and sets Option-as-Meta-key. Evidence at `appleTerminalBackupPath` in config. | Low | ✓ Confirmed (new, macOS-specific) |
| **File** | Prompt/context helper files near repo roots | Low–Medium | ✗ Not observed (state kept in global `~/.claude/`, not project-local) |
| **Network** | TLS/SNI to `api.anthropic.com`, `claude.ai` domains. Note: connections are short-lived HTTPS bursts; polling-based capture (lsof) cannot reliably attribute to claude PID. Requires EDR/ESF process-to-socket correlation or pcap with TLS inspection. | Medium | △ Not directly confirmed (instrumentation gap) |
| **Network** | Request burst cadence matching prompt→response→action cycles | Medium | △ Not directly confirmed (instrumentation gap) |
| **Identity** | OAuth account profile stored in `~/.claude/backups/*.json` — includes email, org UUID, account UUID, org role, billing type, display name in cleartext JSON. Primary identity signal for v2.x+. | High | ✓ Confirmed (new, replaces API key as primary) |
| **Identity** | API key env vars (`ANTHROPIC_API_KEY`) tied to user session. Alternate authentication path; not used when OAuth is active. | Medium | ✗ Not observed (OAuth used instead) |
| **Identity** | Session UUID as cross-artifact correlation key. Single UUID (e.g., `91a4f548-...`) links debug logs, project history, todos, file-history, and session-env. Enables linking file, identity, and behavior evidence to a single session. | High | ✓ Confirmed (new) |
| **Behavior** | Rapid multi-file read/write loops across repo. Observed: 3 files created within <5 seconds — tight temporal clustering confirms burst-write pattern. | High | ✓ Confirmed |
| **Behavior** | Shell command orchestration from AI session context. Observed: pytest execution confirmed by `.pytest_cache/` and compiled `.pyc` artifacts with matching timestamps. | High | ✓ Confirmed |
| **Behavior** | Git commit/patch generation shortly after model interaction. Task-dependent — requires explicit or implicit prompt for git operations. When triggered: `git init` + `git add` + `git commit` in rapid sequence. Commit includes `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer. **⚠ EVASION TESTED (LAB-RUN-EVASION-001): Trailer is trivially suppressible via settings (`includeCoAuthoredBy: false`), git amend/rebase, commit-msg hooks, or filter-branch. High-confidence when PRESENT; zero-confidence when ABSENT. One-way signal only.** | High (present) / None (absent) | ✓ Confirmed + ⚠ Evadable |

#### Signal Quality Weights (from INIT-43, calibration notes from LAB-RUN-001)

| Layer | Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|
| Process | 0.45 | Missing parent chain: −0.15; wrapper/renamed binary: −0.15 | Process identification is clean and unambiguous in standard install. Child chains require <1s monitoring or ESF. |
| File | 0.30 | Stale artifact only: −0.10; non-default paths: −0.10 | File layer is the strongest standalone signal — `~/.claude/` is unique, large (308 files), and appears on first launch. Consider increasing weight to 0.35 in five-layer model. |
| Network | 0.25 | Ambiguous proxy route: −0.10; unresolved proc-net link: −0.10 | Network is weakest signal without EDR. Polling-based capture cannot attribute short-lived HTTPS to claude PID. Consider reducing to 0.20 for polling-only deployments. |

#### Persistence Posture

Claude Code installs **no active persistence mechanisms** — zero LaunchAgents, zero systemd services, zero crontab entries, zero shell profile modifications. All state is passive (config/cache files in `~/.claude/`). This distinguishes it from tools like Ollama (daemon) and is relevant to risk classification.

#### Evasion Vectors
- Renamed binaries / wrapper scripts
- Containerized/WSL execution reducing host visibility
- API traffic through internal relay/proxy
- Shared model gateways obscuring tool attribution
- **✓ Lab Validated (LAB-RUN-EVASION-001):** Co-Authored-By trailer suppression via 6 independent vectors:
  1. **Settings-based:** `includeCoAuthoredBy: false` or `attribution.commit: ""` in `~/.claude/settings.json`, `.claude/settings.json`, or `.claude/settings.local.json` — zero trace, ~5 seconds
  2. **`git commit --amend`** — rewrites commit message post-creation, detectable by hash change
  3. **`git rebase -i`** — rewrites commit during interactive rebase, detectable by hash change
  4. **`commit-msg` hook** — strips trailer before commit object creation. **Most dangerous:** trailer never enters object store, zero forensic trace in git history
  5. **`git filter-branch`** — bulk erases trailers from entire repository history after `refs/original/` cleanup + gc
  6. **Global git template hook** (`init.templatedir`) — automatically strips trailers from all new/cloned repos

#### Evasion Counter-Indicators

Signals that suggest active evasion (add confidence when detected alongside tool presence):

| Indicator | Detection Method | Confidence Boost |
|---|---|---|
| `includeCoAuthoredBy: false` or `attribution.commit: ""` in settings | File scan of `~/.claude/settings.json`, `.claude/settings*.json` | +0.15 (intent) |
| `commit-msg` hook containing `Co-Authored-By` or trailer-stripping patterns | Scan `.git/hooks/` and `core.hooksPath` target | +0.15 (intent) |
| `init.templatedir` pointing to directory with stripping hooks | `git config --global init.templatedir` + template dir scan | +0.20 (systematic intent) |
| Force-push after amend/rebase on branch with known AI activity | Git reflog analysis, push event logs | +0.10 (circumstantial) |

---

### 4.1b Claude Cowork

**Class:** C (Autonomous Executor) in Cowork mode; A (Assistive) in chat-only mode. Exhibits Class D indicators (scheduled tasks via `schedule` skill, self-modification via `skill-creator`, plugin extensibility) but lacks daemon persistence — proactive execution requires app to be running ("soft proactive").  
**Risk Posture:** Medium baseline, High in Cowork mode with MCP connectors and scheduled tasks  
**Lab Validated:** LAB-RUN-014 (2026-03-05, v1.1.4498, macOS ARM64)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | Signed Claude Desktop app process from `/Applications/Claude.app`. macOS: code-signed by `Developer ID Application: Anthropic PBC (Q6L2SF6YDW)`, notarized. Bundle ID: `com.anthropic.claudefordesktop`. Mach-O universal (x86_64 + ARM64). | High | ✓ Confirmed |
| **Process** | Multi-process Electron architecture: main process → GPU helper, Network utility, 2× Plugin helpers (`node.mojom.NodeService` for DXT/MCP extension hosts), 3× Renderers, Crashpad handler. Observed: 12 processes (excl. VM), ~546 MB aggregate RSS. | High | ✓ Confirmed |
| **Process** | Apple `com.apple.Virtualization.VirtualMachine` XPC service running full Linux VM. Spawned by Claude Desktop. 51 MB RSS. **Novel IOC — no other profiled tool runs a VM.** Presence indicates Cowork feature is active. | High | ✓ Confirmed (new) |
| **Process** | `ShipIt` auto-updater (Squirrel.framework) runs as **root**. Privilege escalation vector — update mechanism has higher privileges than the app. | Medium | ✓ Confirmed (new) |
| **File** | `~/Library/Application Support/Claude/` Electron user-data-dir. 10 GB total. Contains: `vm_bundles/` (9.6 GB — VM root filesystem), `local-agent-mode-sessions/`, `Claude Extensions/`, `Cache/`, Cookies, Preferences. **Largest file footprint of any profiled tool.** | High | ✓ Confirmed |
| **File** | VM bundle at `vm_bundles/claudevm.bundle/`: `rootfs.img` (10 GB Linux filesystem), `rootfs.img.zst` (2.1 GB compressed), `efivars.fd` (EFI boot), `macAddress`, `machineIdentifier`, `vmIP`, `sessiondata.img`. Persists after quit. **Pathognomonic for Cowork.** | High | ✓ Confirmed (new) |
| **File** | `claude_desktop_config.json` with Cowork-specific keys: `coworkWebSearchEnabled`, `coworkScheduledTasksEnabled`, `localAgentModeTrustedFolders`, `sidebarMode`. Distinguishes Cowork from Claude Code CLI. | High | ✓ Confirmed |
| **File** | Local agent mode session directories at `local-agent-mode-sessions/<folder-uuid>/<vm-uuid>/local_<session-uuid>.json`. Each session JSON (110–114 KB) contains: `sessionId`, `processName`, `vmProcessName`, `model`, `title`, `initialMessage`, `accountName`, `emailAddress`, `slashCommands`, `remoteMcpServersConfig`, `egressAllowedDomains` (22 domains), `systemPrompt` (42 KB). | High | ✓ Confirmed (new) |
| **File** | Per-session `audit.jsonl` with event types: `assistant`, `user`, `system`, `tool_use_summary`, `rate_limit_event`, `result`. Tool use summaries include natural-language action descriptions. 6–56 events per session. Complete forensic audit trail. | High | ✓ Confirmed (new) |
| **File** | `.claude/` state tree inside each session mirroring Claude Code structure: `.claude.json`, `backups/`, `debug/`, `projects/<path>/session.jsonl`, `shell-snapshots/`, `todos/`. Symlinks point to VM mount paths (`/sessions/<name>/mnt/.claude/`). | Medium–High | ✓ Confirmed (new) |
| **File** | Desktop Extensions (DXT) with MCP servers: `chrome-control` v0.1.5 (browser automation via AppleScript), `notes` v0.1.7 (Apple Notes CRUD). Each has `manifest.json` and Node.js MCP server entry point. | Medium–High | ✓ Confirmed (new) |
| **File** | Skills plugin directory with 6 Anthropic skills: `skill-creator`, `xlsx`, `pptx`, `pdf`, `docx`, `schedule`. Includes full Office XML schemas (ISO-IEC29500), Python scripts, evaluation framework. | Medium–High | ✓ Confirmed (new) |
| **File** | Plugin marketplace git clone from `anthropics/knowledge-work-plugins`. 19+ enterprise plugins (sales, finance, legal, marketing, engineering, HR, etc.) plus partner-built (Slack/Salesforce, Apollo.io, Common Room). | Medium | ✓ Confirmed (new) |
| **Network** | Outbound TLS connections from Network utility process. 15 connections observed: Anthropic API (160.79.104.10), AWS EC2, Google Cloud, `fbcdn.net`. Mix of TCP and UDP (QUIC). **Persistent connections** — PID-attributable at any polling interval (unlike Claude Code CLI's ephemeral bursts). | Medium–High | ✓ Confirmed |
| **Network** | VM egress allowlist in session JSON (`egressAllowedDomains`): 22 domains including package registries (npm, pypi, crates.io), github.com, Ubuntu repos, `*.anthropic.com`, `*.claude.com`. **Novel compliance signal — tool self-reports its own network boundary.** | Medium | ✓ Confirmed (new) |
| **Network** | VM has dedicated IP (`192.168.64.11`) and MAC (`fa:2d:c5:58:59:86`) on Apple Virtualization host-only network. | Low–Medium | ✓ Confirmed (new) |
| **Identity** | `accountName` and `emailAddress` in cleartext in every session JSON. Observed: `"Evan"`, `"evanlewischance@gmail.com"`. **Strongest identity signal of any profiled tool** — top-level JSON field, zero extraction effort. | High | ✓ Confirmed (new) |
| **Identity** | Code signing: `Anthropic PBC (Q6L2SF6YDW)`, same authority as Claude Code CLI. Cryptographic binary attribution via Apple notarization chain. | High | ✓ Confirmed |
| **Identity** | VM `machineIdentifier` (binary plist with UUID). Persists across sessions — device-level identity anchor. Session UUIDs: `sessionId`, `cliSessionId`, `vmProcessName` enable cross-artifact correlation. | Medium–High | ✓ Confirmed (new) |
| **Behavior** | Multi-step agentic execution via MCP connectors. Observed: Google Calendar CRUD (9 tools), Indeed integration (4 tools). 56 audit events in calendar session with 5 tool_use_summary entries. | High | ✓ Confirmed |
| **Behavior** | Shell command execution within VM. Observed via audit trail: architecture check, package installation attempts, file operations. Shell snapshots captured at `shell-snapshots/snapshot-bash-*.sh`. | High | ✓ Confirmed |
| **Behavior** | Scheduled task creation capability. `schedule` skill creates autonomous recurring tasks with cron expressions. Config `coworkScheduledTasksEnabled: true` enables proactive execution while app is running. | Medium–High | ✓ Architecture confirmed |
| **Behavior** | Self-modification via `skill-creator` skill. Creates, modifies, and benchmarks new skills including evaluation framework. No approval gate for skill creation. | Medium–High | ✓ Architecture confirmed |
| **Behavior** | Cross-app automation via DXT extensions. `chrome-control` executes JavaScript in Chrome tabs, reads page content. `notes` accesses Apple Notes. Both run on host via AppleScript (outside VM sandbox). | Medium | ✓ Architecture confirmed |
| **Behavior** | Feature flags in `--desktop-features` process argument JSON: `ccdPlugins`, `chillingSlothFeat`, `yukonSilver`, `plushRaccoon` (unavailable), `quietPenguin` (unavailable). Version fingerprinting and capability prediction. | Low–Medium | ✓ Confirmed (new) |

#### Signal Quality Weights (from LAB-RUN-014, calibration notes)

| Layer | Default Weight | Proposed Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|
| Process | 0.25 | 0.25 | Missing parent chain: −0.15; wrapper/renamed binary: −0.15 | Multi-process Electron + VM XPC service is strong and unique. No other tool has a VM process. |
| File | 0.15 | 0.20 | Stale artifact only: −0.10; non-default paths: −0.10 | 10 GB footprint is largest of any tool. VM bundle is pathognomonic. Session JSONs with audit trails are forensically rich. |
| Network | 0.15 | 0.10 | Ambiguous proxy route: −0.10; unresolved proc-net link: −0.10 | Persistent TLS easily attributed (Network utility centralizes all connections). VM egress allowlist is novel compliance signal. |
| Identity | 0.10 | 0.15 | Weak/missing identity: −0.10 | Cleartext email in session JSON is strongest identity signal of any tool. Upgrade weight. |
| Behavior | 0.15 | 0.10 | No change | Audit trail is strong but app-dependent. Scheduled tasks and self-modification architecturally confirmed but not exercised in this run. |
| Binary Hash | 0.20 | 0.20 | No change | Signed binary is definitive anchor. Same Anthropic authority as Claude Code. |

#### Persistence Posture

Claude Cowork installs **no active persistence mechanisms** — zero LaunchAgents, zero crontab entries, zero shell profile modifications. State is passive (10 GB in `~/Library/Application Support/Claude/`). Scheduled tasks via the `schedule` skill run only while the app is open and do not survive app quit. This distinguishes Cowork from OpenClaw (Class D, LaunchAgent with KeepAlive) but its "soft proactive" capability is unique among non-daemon tools.

#### Evasion Vectors
- Non-standard install path or portable app bundle
- Containerized/remote execution of Claude Desktop
- VPN/proxy obscuring outbound Anthropic API traffic
- Disabling DXT extensions to reduce host-level detection surface
- Using Cowork in VM-only mode without MCP connectors to reduce network signals

---

### 4.2 Cursor (INIT-14)

**Class:** A (SaaS Copilot / Assistive IDE); escalates to C when terminal agent workflows execute  
**Risk Posture:** Medium baseline, High in agentic mode  
**Lab Validated:** LAB-RUN-004 (2026-03-02, v2.5.26, macOS ARM64)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | Signed Cursor app process from standard install paths (`/Applications/Cursor.app`, `%LocalAppData%\Programs\Cursor`). macOS: code-signed by `Developer ID Application: Hilary Stout (VDXQ22DGB9)`, notarized. Bundle ID: `com.todesktop.230313mzl4w4u92`. Mach-O universal (x86_64 + ARM64). | High | ✓ Confirmed |
| **Process** | Multi-process Electron architecture: main process → GPU helper, Network utility, shared-process, terminal pty-host, Renderer (per window), fileWatcher (per window), and three extension-host types per window: (1) `extension-host (user)` — standard extensions, (2) `extension-host (retrieval-always-local)` — AI retrieval with `gitWorker.js`, (3) `extension-host (agent-exec)` — autonomous executor. Observed: 29 processes, ~2.1 GB aggregate RSS. | High | ✓ Confirmed |
| **Process** | **Class C escalation indicator:** `Cursor Helper (Plugin): extension-host (agent-exec)` in process tree. Presence means agent feature is active. Child `/bin/zsh` processes under this host confirm autonomous shell execution. This is the strongest single Class C indicator of any tool tested — directly maps process telemetry to governance class. | High | ✓ Confirmed (new) |
| **Process** | `cursorsan` process on localhost listeners (security/sandbox component). Presence indicates Cursor security features are active. | Medium | ✓ Confirmed (new) |
| **Process** | Sustained session with child process and file-write bursts. Terminal pty-host manages embedded shell sessions; agent-exec spawns `/bin/zsh` with sandbox wrapper (`__CURSOR_SANDBOX_ENV_RESTORE`). | Medium–High | ✓ Confirmed |
| **File** | `~/.cursor/` global config/state directory. Contains: `plans/`, `projects/`, `extensions/`, `ai-tracking/`, `skills-cursor/`. Observed: 63 files, 14 MB. Also: workspace `.cursor/` with project-specific rules (`.mdc` files) and skills. | High | ✓ Confirmed |
| **File** | Agent transcript JSONL files at `~/.cursor/projects/<path-hash>/agent-transcripts/<uuid>/<uuid>.jsonl`. Complete forensic record of agent sessions: prompts, tool calls, file edits, shell commands. Multiple transcripts per project accumulate over time. **Class C artifact** — only created during agent (not assistive) sessions. | High | ✓ Confirmed (new) |
| **File** | `ai-code-tracking.db` — SQLite database at `~/.cursor/ai-tracking/ai-code-tracking.db`. Centralized tracker of all AI-assisted code changes. 4.8 MB observed. Modified during all AI interactions (Class A and C). High-value attribution anchor — one database links all AI activity across all projects. | High | ✓ Confirmed (new) |
| **File** | Agent tools state files at `~/.cursor/projects/<path>/agent-tools/<uuid>.txt`. Stores tool execution state during agent sessions. | Medium | ✓ Confirmed (new) |
| **File** | AI-generated plan files in `~/.cursor/plans/` (e.g., `*.plan.md`). Class A artifacts — evidence of AI planning even without shell execution. | Medium | ✓ Confirmed (new) |
| **File** | Burst edits across repo files with consistent timing. Observed: 3 files in <2s during agentic task. | Medium–High | ✓ Confirmed |
| **Network** | TLS/SNI to Cursor cloud endpoints (`api2.cursor.sh` → `api2geo.cursor.sh` → `api2direct.cursor.sh`, via Cloudflare and AWS). Persistent TLS connections (unlike Claude Code's ephemeral bursts). Connections attributed to specific extension-host PIDs via `lsof` at any polling interval. Extension-host type differentiates Class A (`retrieval-always-local`) from Class C (`agent-exec`) network traffic. | Medium–High | ✓ Confirmed |
| **Network** | Request bursts aligned with prompt-response editing cycles. Multiple concurrent connections to same AI endpoint IP (observed: 4 connections to `54.153.104.1` from single extension host). Persistent connection pattern consistent with HTTP/2 multiplexing. | Medium | ✓ Confirmed (indirect) |
| **Identity** | Cursor account state stored in `~/Library/Application Support/Cursor/` (Electron `--user-data-dir`), **not** in `~/.cursor/`. Detection must check both paths. Account state was not directly captured in LAB-RUN-004 — requires examination of Electron user-data-dir in future run. | Medium | △ Not directly confirmed (stored in different path) |
| **Identity** | Code signing authority as provenance signal: `Developer ID Application: Hilary Stout (VDXQ22DGB9)`, TeamIdentifier `VDXQ22DGB9`. Cryptographic binary attribution via Apple notarization chain. | High | ✓ Confirmed (new) |
| **Behavior** | High-frequency multi-file edit loops after prompt interaction cadence. Observed: 3 source files created within <2s during agentic task. Pattern: prompt → multi-file write fan-out → shell execution → result processing. | High | ✓ Confirmed |
| **Behavior** | Context-heavy reads + concentrated writes (agentic edit shape). Observed: agent read 5 reference files before writing protocol document. Agent-tools state file (91 KB) captured full context window. | High | ✓ Confirmed |
| **Behavior** | Shell invocations proximate to AI edit sequences. Agent-exec → `/bin/zsh` with sandbox wrapper. Shell commands: `mkdir`, heredoc file creation, `python3 -m pytest`, `git init/add/commit`. `.pytest_cache/` and `__pycache__` artifacts confirm execution. | High | ✓ Confirmed |
| **Behavior** | `Made-with: Cursor` git trailer in commits from agent sessions. Analogous to Claude Code's `Co-Authored-By` trailer — one-way signal (high confidence when present, zero when absent). Evasion testing recommended (CUR-EVA-02). | High (present) / None (absent) | ✓ Confirmed (new) |

#### Signal Quality Weights (from LAB-RUN-004, calibration notes)

| Layer | Default Weight | Proposed Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|
| Process | 0.30 | 0.30 | Missing parent chain: −0.15; wrapper/renamed binary: −0.15 | Process tree is the strongest signal. Labeled extension hosts (`agent-exec`) are unique and directly map to governance class. |
| File | 0.20 | 0.20 | Stale artifact only: −0.10; non-default paths: −0.10 | Agent transcripts and ai-tracking.db are high-quality. Smaller file count than Claude Code (63 vs 308) but higher quality per file. |
| Network | 0.15 | 0.20 | Ambiguous proxy route: −0.10; unresolved proc-net link: −0.10 | Persistent TLS easily attributed to PIDs. Extension-host labels enable Class A/C traffic differentiation. Stronger than default assumes. |
| Identity | 0.15 | 0.10 | Weak/missing identity: −0.10 | Account state in Electron user-data-dir was not accessible. OS user is only available signal without deeper inspection. |
| Behavior | 0.20 | 0.20 | No change | Agentic loop confirmed with all three IOCs. `agent-exec` process is binary Class C indicator. |

#### Persistence Posture

Cursor installs **no active persistence mechanisms** — zero LaunchAgents, zero crontab entries, zero shell profile modifications. The app bundle sits in `/Applications/` and state is passive (config/cache files in `~/.cursor/` and `~/Library/Application Support/Cursor/`). This mirrors Claude Code's clean persistence posture and distinguishes both from Ollama (daemon).

#### Evasion Vectors
- Portable/non-standard installs and launch wrappers
- Containerized/remote dev sessions
- Shared model endpoints masking attribution
- Forked/customized builds altering expected artifacts
- `Made-with: Cursor` git trailer suppression (untested — likely via settings, analogous to Claude Code's `Co-Authored-By`)

---

### 4.3 GitHub Copilot (INIT-15)

**Class:** A (SaaS Copilot / Assistive IDE Feature)  
**Risk Posture:** Medium  
**Lab Validated:** LAB-RUN-005 (2026-03-02, github.copilot-chat v0.37.9 in VS Code 1.109.5, macOS ARM64) — unauthenticated baseline

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | IDE host process (VS Code/JetBrains) + Copilot extension host subprocess. VS Code: Electron main → Code Helper (GPU) → Code Helper (Network) → Code Helper (Renderer) → Code Helper (Plugin/ExtHost) → Code Helper (Node). The Plugin helper is the extension host where Copilot loads. **Note:** Extension host process (`Code Helper (Plugin)`) is shared by ALL VS Code extensions — Copilot-specific attribution requires cross-layer correlation with file artifacts or network endpoints. | Medium–High | ✓ Confirmed |
| **Process** | Extension-host activity tied to chat/agent-style workflows. Copilot A/B experiment flags queried on startup (`dwcopilot`, `copilot_t_ci`, `chat`, `edit_mode_hidden`, `use-responses-api`). Agent/edit mode capabilities present in VS Code 1.109.5 but gated behind authentication and feature flags — potential Class A→C escalation path. | Medium | ✓ Confirmed (entitlement check observed; auth-gated) |
| **File** | Copilot extension install directory at `~/.vscode/extensions/github.copilot-chat-<version>/` (lowercase, bundled). Installing `GitHub.copilot` now installs `github.copilot-chat` as a single bundled extension. Contains 242 files including `package.json` manifest and `dist/` bundled JavaScript. | Medium | ✓ Confirmed (updated: single bundled extension, lowercase) |
| **File** | VS Code Application Support data: cached VSIX at `~/Library/Application Support/Code/CachedExtensionVSIXs/github.copilot-chat-<version>`, session logs at `~/Library/Application Support/Code/logs/`, extension state. Persists across VS Code restarts. | Medium | ✓ Confirmed |
| **File** | VS Code `machineId` (SHA-256 device fingerprint) and `devDeviceId` (UUID) in telemetry logs — persistent device-level identity signals present even without GitHub authentication. `machineId` survives reinstalls. | Medium–High | ✓ Confirmed (new) |
| **File** | VS Code telemetry A/B experiment flags including `dwcopilot:<id>` and `copilot_t_ci:<id>` — reveals Copilot feature state and can be used for version fingerprinting. | Low–Medium | ✓ Confirmed (new) |
| **Network** | Traffic to `copilot-proxy.githubusercontent.com`, GitHub Copilot API endpoints. All VS Code network traffic flows through a dedicated `Code Helper` Network Service process — process-to-socket attribution is trivial via `lsof`. Connections are persistent (ESTABLISHED), unlike Claude Code's ephemeral HTTPS bursts. IP ranges: 13.107.x.x, 150.171.x.x (Microsoft/GitHub infrastructure). | Medium | △ Partially confirmed (IPs observed, specific Copilot endpoints need TLS/SNI) |
| **Network** | Burst timing aligned with suggestion/chat activity | Low–Medium | ✗ Not observed (unauthenticated — no inference traffic) |
| **Identity** | GitHub account auth state (org-managed vs personal). When authenticated, tokens stored in macOS Keychain under `vscodevscode.github-authentication`. `GitHub Authentication.log` records explicit session state — "Got 0 sessions" when unauthenticated. **Bimodal confidence:** strongest layer when authenticated (~0.90), weakest when not (~0.40). | High | △ Partially confirmed (negative state captured: 0 sessions, no keychain entry) |
| **Identity** | License/entitlement context from org policy. `chatEntitlement` and `chatRegistered` fields in VS Code telemetry distinguish three states: (a) not installed (`chatEntitlement: 0`), (b) installed but not authenticated (`chatEntitlement: 1, chatRegistered: 0`), (c) active (`chatEntitlement: 1, chatRegistered: 1`). | High | ✓ Confirmed (state b observed) |
| **Behavior** | Suggestion acceptance cadence + rapid edit bursts | Medium | ✗ Not observed (unauthenticated) |
| **Behavior** | AI-chat-to-edit sequences across multiple files | Medium–High | ✗ Not observed (unauthenticated) |
| **Behavior** | High-volume generated changes without normal review cadence | High (risk marker) | ✗ Not observed (unauthenticated) |
| **Behavior** | Passive behavioral signal: Copilot experiment flag queries on VS Code startup indicate extension presence even without active usage. | Low | ✓ Confirmed (new) |

#### Signal Quality Weights (from LAB-RUN-005, calibration notes)

| Layer | Default Weight | Proposed (Unauth) | Proposed (Auth) | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|---|
| Process | 0.30 | 0.25 | 0.20 | Extension-host shared by all extensions: −0.05 | Extension host is shared — less distinctive than standalone processes. De-emphasize when identity is available. |
| File | 0.20 | 0.25 | 0.20 | Stale artifact only: −0.10; non-default paths: −0.10 | Extension directory and telemetry logs are strong, unique. machineId/devDeviceId provide persistent device identity. |
| Network | 0.15 | 0.15 | 0.15 | Ambiguous proxy route: −0.10; unresolved proc-net link: −0.10 | Persistent connections easy to detect. Endpoint attribution needs TLS/SNI. |
| Identity | 0.15 | 0.15 | 0.25 | Weak/missing identity: −0.10 | **Bimodal:** strongest layer when authenticated (org-managed GitHub), weakest without. Increase weight for authenticated scenarios — primary governance lever for Class A. |
| Behavior | 0.20 | 0.20 | 0.20 | No change | Should be strong when active. Passive flag queries provide minimal signal. |

#### Persistence Posture

Copilot installs **no active persistence mechanisms** — zero LaunchAgents, zero crontab entries, zero shell profile modifications. The extension resides in `~/.vscode/extensions/` and cached data in `~/Library/Application Support/Code/`. VS Code itself (when installed via Homebrew cask) sits in `/Applications/` with no auto-start. This mirrors Claude Code and Cursor's clean persistence postures.

#### Evasion Vectors
- Personal GitHub accounts on managed endpoints (primary governance concern — no mechanism to prevent without MDM/IdP integration)
- Remote dev containers with partial host telemetry
- Extension forks/alternate clients
- Shared endpoints with weak identity correlation
- Unauthenticated installation creating dormant tool presence on managed endpoints

---

### 4.4 Ollama (INIT-16)

**Class:** B (Local Model Runtime)  
**Risk Posture:** Medium (perimeter blind spot)  
**Lab Validated:** LAB-RUN-003 (2026-02-26, v0.17.0, macOS ARM64)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | `ollama serve` daemon process running on host. Binary: Mach-O ARM64 at `/opt/homebrew/bin/ollama` (brew) or system path (Linux script). Long-lived process, direct child of `launchd`/`systemd`. | High | ✓ Confirmed |
| **Process** | CLI invocations: `ollama run`, `ollama pull`, `ollama serve`, `ollama list`. Note: CLI commands are **HTTP clients** of the daemon, not child processes — they connect via `localhost:11434`. Detection should monitor daemon and CLI invocations independently. | High | ✓ Confirmed |
| **Process** | Brew service registration visible in `brew services list` (macOS). Indicates tool is installed and available for daemon operation even when not running. | Medium | ✓ Confirmed (new) |
| **File** | Model storage: `~/.ollama/models/` directory with content-addressable blobs (SHA-256) and OCI-format manifests at `manifests/registry.ollama.ai/library/<model>/<tag>`. Observed: 652 MB after two models (13 files). Manifests follow Docker distribution manifest v2 with custom Ollama media types (`application/vnd.ollama.image.model`, `.template`, `.system`, `.params`). | High | ✓ Confirmed |
| **File** | Pulled model metadata, version/tag files, pull timestamps. API endpoint `/api/tags` returns complete model inventory: name, digest, size, family, parameter count, quantization level. | High | ✓ Confirmed |
| **File** | Ed25519 keypair (`~/.ollama/id_ed25519`, `id_ed25519.pub`) generated on **first `serve`**, not during install. Presence indicates the tool has been *run*, not merely installed. Purpose: likely registry authentication/identity. | Medium–High | ✓ Confirmed (new) |
| **File** | `~/.ollama/` data directory created on first `serve`, not during install. Absence after install does not indicate absence of tool. Contains: `id_ed25519`, `id_ed25519.pub`, `models/blobs/`, `models/manifests/`. | High | ✓ Confirmed (new) |
| **File** | Cache/artifact growth patterns indicating active inference. Model storage grows with each pull. No ephemeral inference cache observed — Ollama holds model state in memory during inference. | Medium | ✓ Confirmed |
| **Network** | Localhost API listener on default `:11434` (TCP, IPv4). **Unauthenticated** — any local process can invoke inference, pull models, or query inventory without credentials. Process-to-socket attribution is clean and trivial via `lsof` at any polling interval (persistent listener, unlike short-lived HTTPS). | High | ✓ Confirmed (upgraded from Medium) |
| **Network** | Outbound model pull traffic to `registry.ollama.ai`. Large, distinctive downloads (637 MB for tinyllama). After initial pull, operates entirely locally with zero outbound network activity — confirms "perimeter blind spot" risk classification. | Medium | ✓ Confirmed |
| **Identity** | OS user/session tied to daemon and CLI interactions. No dedicated system user on macOS/brew (daemon runs under installing user). Linux install script typically creates an `ollama` system user — platform-specific difference. No account system, API keys, or OAuth — identity is limited to OS process ownership. | Medium | ✓ Confirmed (with caveats) |
| **Behavior** | Repeated prompt/inference cycles via local API/CLI. Observed: single inference at 85ms, 5-request burst in ~24s. Inference burst cadence on localhost is a distinctive behavioral signal. | High | ✓ Confirmed |
| **Behavior** | Automation scripts invoking local generation against repos/data. Observed: curl script reading local `.py` file and sending to `/api/generate` for analysis. Script-to-API chain is itself a behavioral signal. | High | ✓ Confirmed |
| **Behavior** | Unsanctioned model pulls and rapid model switching. Observed: two models pulled (tinyllama generative + all-minilm embedding) with immediate switching between inference targets. | High (risk marker) | ✓ Confirmed |

#### Signal Quality Weights (from LAB-RUN-003, calibration notes)

| Layer | Default Weight | Proposed Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|
| Process | 0.30 | 0.25 | Missing daemon process: −0.15; wrapper/renamed binary: −0.15 | Daemon is easily detectable but less distinctive than CLI tools — many services listen on localhost. |
| File | 0.20 | 0.25 | Stale artifact only: −0.10; non-default paths: −0.10 | Model storage is large, unique, and persistent. Content-addressable blobs are distinctive. Consider weight increase. |
| Network | 0.15 | 0.20 | Custom port (non-11434): −0.05; ambiguous proxy route: −0.10 | Persistent localhost listener is trivially detectable (inverts difficulty vs Class C HTTPS bursts). |
| Identity | 0.15 | 0.10 | Weak/missing identity correlation: −0.10 | Architecturally weak — no account system. Inherent ceiling for Class B tools. |
| Behavior | 0.20 | 0.20 | No change | Inference burst cadence and model management are solid behavioral signals. |

#### Persistence Posture

Ollama's persistence behavior differs significantly by install method:
- **macOS (Homebrew):** Registers as a brew service (visible in `brew services list`) but does **not** install a LaunchAgent/LaunchDaemon or auto-start. Daemon only runs when manually started or explicitly enabled via `brew services start ollama`. Zero shell profile modifications, zero crontab entries.
- **macOS (Direct download):** Installs as a macOS app with LaunchAgent for auto-start.
- **Linux (install script):** Creates a `systemd` service with auto-start, and a dedicated `ollama` system user.
- **All platforms:** Model storage in `~/.ollama/models/` persists across daemon restarts, reboots, and even daemon uninstall. Models are available for offline use indefinitely.

#### Evasion Vectors
- Custom ports or wrapped execution paths
- Containerized Ollama instances
- Side-loaded model files with renamed tags
- Offline model use after initial pull
- Binding API to `0.0.0.0` for remote access (via `OLLAMA_HOST` env var)

---

### 4.5 LM Studio (INIT-17)

**Class:** B (Local Model Runtime)  
**Risk Posture:** Medium (perimeter blind spot)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | LM Studio desktop app process (signed binary from standard install) | High |
| **Process** | Child process activity during model loading/inference | Medium |
| **File** | Local model storage (downloaded GGUF/safetensors files) | High |
| **File** | App configuration/workspace files with model selections | Medium |
| **File** | Cache growth and model-switching traces | Medium |
| **Network** | Local loopback API traffic (when local server mode enabled) | Medium |
| **Network** | Outbound model download traffic (Hugging Face, etc.) | Medium |
| **Identity** | Endpoint user session mapped to LM Studio actions | Medium |
| **Behavior** | Repeated local inference loops | High |
| **Behavior** | Model switching patterns | Medium |
| **Behavior** | Sensitive file reads preceding local inference sessions | High (risk marker) |

#### Evasion Vectors
- Custom model paths and renamed artifacts
- Local server on non-default ports
- Containerized/packaged execution
- Offline usage after initial model acquisition

---

### 4.6 Continue (INIT-18)

**Class:** A (Assistive IDE Extension) — but backend-agnostic, so risk scales with config  
**Risk Posture:** Medium; escalates if routing to unapproved backends

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | IDE host + extension host activity associated with Continue | Medium |
| **Process** | Extension-triggered file edits and terminal usage | Medium |
| **File** | Continue extension install manifests (`extensions/Continue*`) | Medium |
| **File** | `config.json` / `config.yaml` specifying model backends/providers | High (attribution-critical) |
| **File** | Workspace/local cache artifacts showing interaction windows | Medium |
| **Network** | Outbound calls to configured model targets (varies per config) | Medium |
| **Network** | Traffic bursts synchronized with extension activity | Low–Medium |
| **Identity** | Credential source and backend ownership context | Medium |
| **Behavior** | Prompt-to-edit loops in IDE files | Medium–High |
| **Behavior** | Extension-driven multi-file modifications | Medium–High |
| **Behavior** | Use of unapproved backend with sensitive repo context | High (risk marker) |

**Key distinction:** Continue's backend is user-configurable, so domain allowlists are brittle. Config file analysis is the primary attribution mechanism.

#### Evasion Vectors
- Custom/forked extension builds
- Hidden/templated config routing to unsanctioned endpoints
- Shared internal gateways obscuring backend
- Remote dev with partial host telemetry

---

### 4.7 Open Interpreter (INIT-19)

**Class:** C (Autonomous Executor)  
**Risk Posture:** High — executes shell commands and manipulates host resources directly  
**Lab Validated:** LAB-RUN-006 (2026-03-02, v0.4.3, macOS ARM64, Ollama local backend)

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | Python runtime mapped to Open Interpreter entrypoints/modules. **Process appears as `python3` in process listings, NOT as `interpreter`.** Detection requires matching Python processes with `interpreter.terminal_interface` or `open-interpreter` in module paths or command arguments. Entrypoint is a console_script at `<venv>/bin/interpreter`. | High | ✓ Confirmed (with caveat: generic process name) |
| **Process** | Parent lineage: terminal → python3 (interpreter) → python3 (ipykernel_launcher) → bash → child commands (pip/pytest/etc). **OI uses Jupyter/IPyKernel as its code execution substrate** — this adds an indirection layer not present in Claude Code. Detection should look for IPyKernel child of a Python process with interpreter module path. | High | ✓ Confirmed (architecture different from predicted) |
| **Process** | Privilege context: effective uid/admin elevation during sessions. No privilege escalation observed for scoped tasks, but with `auto_run=True` nothing prevents `sudo` if the model generates it — safety boundary is entirely LLM-dependent. | High (risk marker) | ✓ Confirmed (no escalation in test) |
| **File** | `open-interpreter` package in venv/site-packages. **Venv location is user-chosen and arbitrary** — no fixed path like `~/.claude/`. Artifact sweeps must search for `interpreter` package across all Python environments (system, user, venv, conda). | High | ✓ Confirmed |
| **File** | Distinctive dependency fingerprint: `litellm` + multi-provider SDKs (`anthropic`, `openai`, `google-generativeai`) + `selenium` + `tiktoken` + `ipykernel`. 135+ packages, 590 MB venv. This combination is unlikely outside AI tool contexts. | Medium | ✓ Confirmed (new) |
| **File** | Session history/transcript artifacts. **v0.4.3 stores NO persistent state outside the virtualenv.** No `~/.config/open-interpreter/`, no session logs. Ephemeral session model — all state lost when venv is deleted. Contrast with Claude Code (308 persistent files in `~/.claude/`). | Medium | ✗ Not observed (architecturally absent) |
| **File** | Short-window file write bursts aligned with command execution. Observed: 2 source files + test artifacts created within seconds. Task-dependent. | Medium | ✓ Confirmed |
| **Network** | Model-provider API calls with burst timing matching action loops. **Provider target varies by configuration:** may connect to `api.openai.com`, `api.anthropic.com`, `localhost:11434` (Ollama), or custom endpoints. Network IOC must match on traffic pattern (burst timing) rather than fixed destination. Tool can transparently switch providers. | Medium | ✓ Confirmed (localhost:11434 via Ollama fallback) |
| **Network** | Outbound requests triggered as part of command workflows. Observed: `pip install` from within agentic session triggered PyPI downloads. Secondary network activity from command execution is a useful corroborative signal. | Medium | ✓ Confirmed |
| **Identity** | Endpoint user identity mapped to interpreter runtime session. OS user (uid) clearly attributable via `ps`/`lsof`. | Medium | ✓ Confirmed |
| **Identity** | Credential/token exposure in runtime environment. API keys passed via env vars are accessible to ALL child processes spawned by OI (including shell commands). **Runtime credential exposure is broader than Claude Code's OAuth model.** However, no credentials persist to disk — forensic credential recovery is not possible. | High (risk marker) | ✓ Confirmed (structural, not persisted) |
| **Behavior** | Plan→execute→revise loops with command bursts. LLM generates tool call → OI executes → output captured → next step. | High | ✓ Confirmed |
| **Behavior** | Repeated shell/file operations with low inter-command delay. 5 operations in ~30 seconds without human review. | High | ✓ Confirmed |
| **Behavior** | Package install + execution chain in same loop. `pip install flask pytest` followed immediately by `pytest test_app.py` in a single session. **Primary risk marker for Open Interpreter.** | High (risk marker) | ✓ Confirmed |
| **Behavior** | Credential-store touches / broad file fan-out in restricted paths. Task-dependent — not triggered for scoped lab task. | High (risk marker) | ✗ Not observed (task-dependent) |
| **Behavior** | `auto_run=True` / `-y` flag enabling unconfirmed execution. Disables ALL execution confirmation prompts. Detection of this flag in process arguments or configuration is itself a high-risk signal. | High (risk marker) | ✓ Confirmed (new) |

#### Signal Quality Weights (from LAB-RUN-006, calibration notes)

| Layer | Default Weight | Proposed Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|
| Process | 0.30 | 0.25 | Missing parent chain: −0.15; wrapper binary: −0.15 | Generic `python3` name reduces process-layer value. IPyKernel mediation adds indirection. Module-path matching required. |
| File | 0.20 | 0.15 | Stale artifact: −0.10; non-default paths: −0.10 | Ephemeral session model — zero state outside venv. Venv location arbitrary. Weakest file layer of any tested tool. |
| Network | 0.15 | 0.15 | Ambiguous proxy: −0.10; unresolved proc-net: −0.10 | Provider-dependent target, same polling challenges as Claude Code. No change from default. |
| Identity | 0.15 | 0.10 | Weak identity: −0.10 | Env-var credentials only, no persistent identity store. Weaker than Claude Code OAuth. |
| Behavior | 0.20 | 0.35 | No specific penalty | **Dominant signal.** Command-chain pattern is the primary detection anchor. Package-install-then-execute is highly distinctive. |

#### Persistence Posture

Open Interpreter installs **no active persistence mechanisms** and **no persistent state directories**. Zero LaunchAgents, zero crontab entries, zero shell profile modifications, zero config directories outside the virtualenv. The entire footprint is contained within the venv and workspace. Deleting the venv eliminates nearly all forensic evidence. This is the most ephemeral of all tested tools.

#### Evasion Vectors
- Wrapper scripts masking invocation semantics
- Renamed/forked package distributions
- Containerized/remote execution
- **Ephemeral virtualenv reducing artifact persistence** — venv can be created anywhere with any name, and deleting it removes all tool artifacts
- `python -m interpreter` invocation bypassing the named entrypoint
- Generic `python3` process name obscuring tool identity in process listings
- Silent model provider switching (cloud ↔ local) changing network fingerprint

---

### 4.8 Aider (INIT-20)

**Class:** C (Autonomous Executor — repo mutation focus)  
**Risk Posture:** Medium-High — high-impact code changes + git operations at speed

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | `aider` CLI invocation from terminal | High |
| **Process** | Parent-child: terminal → aider → git/shell/test subprocesses | High |
| **Process** | Session loops: repeated prompt-edit-diff cycles | Medium–High |
| **File** | Concentrated source-file edit bursts in narrow time windows | High |
| **File** | Repeated patch/rewrite across related modules | Medium |
| **File** | `.aider*` session/config artifacts | Medium |
| **Network** | Model endpoint traffic aligned with active aider sessions | Medium |
| **Identity** | OS user session + git author identity correlation | High |
| **Identity** | Branch protection applicability to actor/repo | High (governance-critical) |
| **Behavior** | Prompt-edit-commit loops with short latency | High |
| **Behavior** | Rapid iterative diff generation before commit | High |
| **Behavior** | Direct writes to protected branches without review | High (risk marker) |

#### Evasion Vectors
- Wrapper scripts / shell aliases
- Renamed aliases and shell functions
- Remote dev containers
- Post-processing scripts obscuring edit source

---

### 4.9 GPT-Pilot (INIT-21)

**Class:** C (Autonomous Executor — project-generation/orchestration)  
**Risk Posture:** High — large-scale code generation and workflow automation

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | Orchestrator runtime (python/node launcher) with long-lived execution | High |
| **Process** | Repeated generate→run→correct child process cycles | High |
| **Process** | Child process categories: build/test/package/file ops | Medium |
| **File** | Sudden project tree creation from sparse baseline | High |
| **File** | High fan-out file generation bursts in short windows | High |
| **File** | Scaffold/template residue and run-state artifacts | Medium |
| **Network** | API burst cycles aligned with generation phases | Medium |
| **Network** | Dependency download/network actions from generated setup flows | Medium |
| **Identity** | Actor/session tied to orchestrator process and workspace | Medium |
| **Behavior** | Generate→validate→regenerate loops | High |
| **Behavior** | Broad write patterns with high file churn velocity | High |
| **Behavior** | Mass overwrite of pre-existing code | High (risk marker) |
| **Behavior** | Generation in protected monorepo roots | High (risk marker) |

#### Evasion Vectors
- Custom forks and renamed launchers
- Containerized isolated runs
- Artifact relocation/cleanup post-run
- Shared model gateways

---

### 4.10 Cline (INIT-22)

**Class:** C (IDE-embedded Autonomous Assistant) when tool-calling is active; A otherwise  
**Risk Posture:** High in sensitive repos due to external tool calls + broad context access

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | IDE + extension host process activity tied to Cline | Medium–High |
| **Process** | Parent-child: extension host → shell/tool subprocesses | High |
| **File** | Cline extension manifests/version fingerprints | Medium |
| **File** | Workspace config/state files indicating tool-calling settings | High (attribution-critical) |
| **File** | Session-window file fan-out tied to assistant actions | Medium |
| **Network** | Backend model endpoint traffic aligned with extension activity | Medium |
| **Network** | Tool-call side traffic where external integrations are used | Medium |
| **Identity** | Actor-session mapping to IDE process and extension use | Medium |
| **Behavior** | Prompt→plan→edit/tool-call loop sequencing | High |
| **Behavior** | Broad context reads followed by focused multi-file writes | High |
| **Behavior** | External tool calls from sensitive repositories | High (risk marker) |

#### Evasion Vectors
- Forked/renamed extension builds
- Custom backend routing through shared proxies
- Remote/containerized dev reducing host visibility
- Config drift to unsanctioned tool-call settings

---

### 4.11 OpenClaw

**Class:** D (Persistent Autonomous Agent)  
**Risk Posture:** Critical — always-on autonomous agent with full system access, self-modification capability, multi-channel external communication, and proactive/scheduled execution  
**Lab Validated:** LAB-RUN-007 (2026-03-02, v2026.3.1, macOS ARM64, cloud LLM: gpt-5.3-codex), LAB-RUN-013 (2026-03-05, v2026.3.1, macOS ARM64, local LLM: Qwen 3.5 0.8B via Ollama)

> **Class D Reference Implementation.** OpenClaw is the first tool to satisfy all four Class D criteria: (1) daemon persistence via LaunchAgent with `KeepAlive + RunAtLoad`, (2) proactive/scheduled execution via cron/heartbeat infrastructure, (3) external communication channels (WhatsApp, Telegram, Slack), and (4) self-modification (agent writes and hot-reloads its own skills). See Section 5.1 for the Class D taxonomy definition.

#### Concrete IOCs

| Layer | Indicator | Confidence Weight | Lab Status |
|---|---|---|---|
| **Process** | `openclaw` CLI binary (Node.js) and `openclaw gateway` long-lived daemon process. Binary at npm global path (e.g., `/opt/homebrew/bin/openclaw`). Gateway runs as persistent Node.js process. Parent chain: `launchd` → `node` (gateway) when daemon-installed, or terminal → shell → `openclaw` for CLI invocations. | High | ✓ Confirmed |
| **Process** | Child process chains during agentic execution: gateway → shell → commands. Browser automation spawns Chrome/Chromium child processes (CDP-controlled). Skill execution may spawn additional child processes. | High | ✓ Confirmed |
| **Process** | Persistent daemon process (launchd LaunchAgent on macOS, systemd user service on Linux). Unlike Claude Code (on-demand), OpenClaw is designed to run 24/7. `openclaw status` reveals daemon state. | High (persistence marker) | ✓ Confirmed |
| **Process** | Cron/scheduled task execution — agent-initiated actions without user prompt. Gateway runs cron jobs that trigger agent turns autonomously. | High (risk marker) | △ Architecture confirmed; not exercised in lab |
| **File** | `~/.openclaw/` global config/state directory. Created during `openclaw onboard`. Contains: `openclaw.json` (main config), `workspace/` (agent workspace + skills), `agents/` (agent state + sessions), `credentials/` (channel auth tokens). | High | ✓ Confirmed |
| **File** | `~/.openclaw/openclaw.json` — central configuration file with model provider, channel tokens, gateway settings, skill configuration. Contains API keys and bot tokens in cleartext JSON. High-value identity and configuration artifact. | High | ✓ Confirmed |
| **File** | `~/.openclaw/workspace/skills/` — user-created and managed skills. Skills are Markdown files (`SKILL.md`) that define tool behavior. **Self-modification surface:** the agent can write new skills here and they are hot-reloaded. | High (risk marker) | ✓ Confirmed |
| **File** | `~/.openclaw/credentials/` — channel authentication stores (WhatsApp session data, bot tokens). Presence indicates active messaging platform connections. | High | ✓ Confirmed (directory created) |
| **File** | `~/.openclaw/agents/default/sessions/` — persistent session/conversation history across restarts and channels. Forensic value: contains complete interaction transcripts. | Medium–High | ✓ Confirmed |
| **File** | LaunchAgent plist at `~/Library/LaunchAgents/` (macOS) or systemd unit (Linux). Installed by `openclaw onboard --install-daemon`. Enables auto-start on boot. | High (persistence marker) | ✓ Confirmed |
| **File** | Workspace prompt injection files: `AGENTS.md`, `SOUL.md`, `TOOLS.md` in `~/.openclaw/workspace/`. Define agent persona and capabilities. | Medium | ✓ Confirmed |
| **Network** | Gateway WebSocket listener on `ws://127.0.0.1:18789` (default). All clients, channels, and tools connect through this. Analogous to Ollama's `:11434` but WebSocket-based. | High | ✓ Confirmed |
| **Network** | Model provider API traffic — destination varies by configuration: `api.anthropic.com`, `api.openai.com`, `api.deepseek.com`, `generativelanguage.googleapis.com`, or localhost (Ollama). Burst cadence matching prompt→response→action cycles. **Local LLM variant (LAB-RUN-013):** with Ollama backend, inference traffic is entirely `127.0.0.1 → 127.0.0.1:11434`. Gateway still makes outbound `:443` connections for telemetry/channel keepalive even with a fully local model. Absence of cloud API traffic does NOT equal absence of network signals. | Medium | ✓ Confirmed (cloud + local variants) |
| **Network** | Chat platform connections — WhatsApp Web (Baileys library, persistent WebSocket), Telegram Bot API, Discord gateway (WebSocket), Slack (Bolt WebSocket), Signal (signal-cli). These are persistent outbound connections that survive across sessions. **Novel IOC not present in any other profiled tool.** | High | △ Architecture confirmed; WhatsApp/Telegram not connected in lab |
| **Network** | Browser automation traffic — CDP connections to managed Chrome/Chromium. Outbound HTTP/HTTPS from browser sessions to arbitrary destinations. | Medium | ✓ Confirmed (browser tool available) |
| **Network** | Skill download traffic — ClawHub registry (`clawhub.com`) for managed skill acquisition. | Low–Medium | Not tested |
| **Identity** | Model provider API keys in `~/.openclaw/openclaw.json` or environment variables. Multiple keys may be present (Anthropic + OpenAI + others). | High | ✓ Confirmed |
| **Identity** | Chat platform bot tokens/credentials in config or `~/.openclaw/credentials/`. WhatsApp session auth, Telegram bot tokens, Discord bot tokens, Slack app tokens. | High | ✓ Confirmed (config structure observed) |
| **Identity** | OS user running the daemon. Gateway process ownership visible via `ps`/`lsof`. | Medium | ✓ Confirmed |
| **Behavior** | Proactive execution without user prompt — cron-triggered agent turns, heartbeat check-ins, webhook-triggered actions. **Novel behavior: the agent acts autonomously on a schedule, not in response to a user command.** | High (risk marker) | △ Architecture confirmed; not exercised in lab |
| **Behavior** | Self-modification — agent writes new skills (Markdown + code) to `~/.openclaw/workspace/skills/`, which are hot-reloaded by the skill watcher. **Highest-risk behavioral pattern in the playbook.** | High (risk marker) | ✓ Confirmed |
| **Behavior** | Shell command execution from agent context. Full system access: reads/writes files, executes arbitrary commands. Comparable to Claude Code and Open Interpreter but always-on. | High | ✓ Confirmed |
| **Behavior** | Multi-channel message routing — a single prompt from WhatsApp/Telegram/Discord can trigger file operations, shell commands, and browser automation on the host. External input → local execution pipeline. | High (risk marker) | △ Architecture confirmed; not connected in lab |
| **Behavior** | Browser automation sessions — agent navigates web, fills forms, extracts data via managed Chromium. Creates detection surface not present in other Class C tools. | Medium–High | ✓ Confirmed (browser tool available) |
| **Behavior** | Rapid multi-file read/write during agentic tasks. File fan-out patterns similar to Claude Code but potentially triggered by external messages, not local prompts. | High | ✓ Confirmed |

#### Signal Quality Weights (from LAB-RUN-007, calibration notes)

| Layer | Default Weight | Proposed Weight | Key Penalty Conditions | Lab Calibration Notes |
|---|---|---|---|---|
| Process | 0.30 | 0.25 | Missing parent chain: −0.15; wrapper binary: −0.15 | Named `openclaw` binary is clear signal. Daemon + CLI dual process model (like Ollama). |
| File | 0.20 | 0.30 | Stale artifact: −0.10; non-default paths: −0.10 | Richest file footprint of any tested tool. Config, credentials, skills, sessions, workspace, LaunchAgent. |
| Network | 0.15 | 0.15 | Ambiguous proxy: −0.10; unresolved proc-net: −0.10 | Gateway listener is strong signal. Model provider traffic varies. Chat platform connections are novel. |
| Identity | 0.15 | 0.15 | Weak identity: −0.10 | Strongest identity footprint of any tested tool: API keys + bot tokens + channel credentials in config. |
| Behavior | 0.20 | 0.15 | No specific penalty | Behavioral signals are present but less dominant than file layer. Proactive/scheduled behavior is the novel signal. **Model-dependent:** LAB-RUN-013 showed that a 0.8B model could not trigger tool-use behavioral IOCs (shell execution, self-modification). Behavior signal dropped from 0.80 to 0.40 with a small model. Infrastructure IOCs (process, file, identity) are model-independent. |

#### Persistence Posture

OpenClaw has the **strongest persistence posture of any profiled tool**:

- **Active daemon:** LaunchAgent (macOS) or systemd user service (Linux) installed by `openclaw onboard --install-daemon`. Auto-starts on boot.
- **Persistent state:** `~/.openclaw/` contains config, credentials, session history, skills, and workspace across restarts.
- **Persistent connections:** Chat platform WebSocket connections maintained by the gateway daemon.
- **Scheduled execution:** Cron jobs and webhooks enable the agent to act without user presence.

This combines Ollama's daemon persistence with Claude Code's rich state directory and adds proactive scheduling — a persistence profile not seen in any other tool.

#### Evasion Vectors

- Renamed binary or wrapper scripts masking `openclaw` invocation
- Custom gateway port (non-default `18789`) reducing network signature
- Non-default config directory via environment variables
- Containerized/remote gateway execution (Docker, remote Linux instance)
- Local model backend (Ollama) eliminating cloud API network fingerprint
- Disabled or selective channel connections reducing network footprint
- Skills with obfuscated names/purposes
- Ephemeral gateway mode (no `--install-daemon`) leaving no LaunchAgent/systemd trace

---

### IOC Summary: Quick-Reference Matrix

| Tool | Primary Process Signal | Key File Artifact | Key Network Indicator | Risk Class |
|---|---|---|---|---|
| Claude Code | `claude` CLI binary + child chains | `~/.claude/` config/state dirs | `api.anthropic.com` | C |
| Cursor | Signed `Cursor` app + `agent-exec` extension host (Class C indicator) | `~/.cursor/` (agent transcripts, ai-tracking.db) | Persistent TLS to `api2.cursor.sh` (PID-attributable) | A→C |
| Copilot | IDE + Copilot extension host subprocess (shared `Code Helper (Plugin)`) | `~/.vscode/extensions/github.copilot-chat-*` + VS Code telemetry (machineId, experiment flags) | Persistent HTTPS to Microsoft/GitHub IPs via Network Service helper | A |
| Ollama | `ollama serve` daemon + CLI clients (HTTP, not child procs) | `~/.ollama/models/` (OCI blobs) + ed25519 keypair | Localhost `:11434` (unauth), `registry.ollama.ai` | B |
| LM Studio | LM Studio desktop process | Local model storage (GGUF files) | Loopback API, HuggingFace pulls | B |
| Continue | IDE + Continue extension host | `config.json` with backend targets | Varies per config | A→C |
| Open Interp. | `python3` (generic name) + interpreter module via IPyKernel | venv/site-packages (**zero persistent state**) | Model provider APIs (varies by config) | C |
| Aider | `aider` CLI + git subprocesses | `.aider*` config, concentrated edits | Model endpoint traffic | C |
| GPT-Pilot | Long-lived orchestrator process | Project tree generation artifacts | API bursts + dependency pulls | C |
| Cline | IDE + Cline extension host | Extension manifests + tool-call config | Backend model + tool-call traffic | A→C |
| **OpenClaw** | **`openclaw` gateway daemon (Node.js) + CLI** | **`~/.openclaw/` (config, credentials, skills, sessions, workspace) + LaunchAgent** | **Gateway `ws://127.0.0.1:18789` + model API + chat platform WebSockets** | **D** |

---

## 5. Tool Class Policy Model

*Source: INIT-23*

Governance targets **capability and risk surface**, not product names. This makes controls resilient to forks, wrappers, and tool churn.

### 5.1 Class Taxonomy

#### Class A — SaaS Copilots / Assistive IDE Features
**Representatives:** Copilot, Cursor (cloud-assist mode), Continue (approved backend)

| Attribute | Value |
|---|---|
| Core behavior | Suggestion/chat assistance, bounded to IDE context |
| Primary risks | Code/data leakage, sensitive context exposure, uncontrolled repo usage |
| Default controls | Org-account requirement, repo/path restrictions, DLP content controls, logging |
| Default posture | Detect/Warn baseline → Approval Required for sensitive scope |

#### Class B — Local Model Runtimes
**Representatives:** Ollama, LM Studio

| Attribute | Value |
|---|---|
| Core behavior | Local inference + model storage, localhost/service operation |
| Primary risks | Perimeter-control blind spots, unapproved models, local sensitive data processing |
| Default controls | Model allowlist + source/checksum policy, endpoint posture, model inventory monitoring |
| Default posture | Detect for first-seen → Warn for unapproved → Block for restricted context violation |

#### Class C — Autonomous Executors / Agentic Operators
**Representatives:** Open Interpreter, Aider, GPT-Pilot, Cline (tool-calling), Claude Code (agentic mode)

| Attribute | Value |
|---|---|
| Core behavior | Command execution, broad file/process/network interaction, autonomous loops |
| Primary risks | Privileged/destructive commands, high-fan-out mutation, boundary crossing, exfiltration |
| Default controls | Command allow/deny, privileged action step-up, protected path restrictions, immutable audit |
| Default posture | Warn/Approval Required sooner; Block thresholds stricter for sensitive targets |

#### Class D — Persistent Autonomous Agents
**Representatives:** OpenClaw

| Attribute | Value |
|---|---|
| Core behavior | Always-on daemon execution + Class C autonomous actions + external message channels + self-modification |
| Primary risks | Persistent attack surface (no off-state), external prompt injection via chat platforms, credential exposure in daemon config, unapproved capability self-modification, proactive execution without user presence |
| Default controls | All Class C controls + daemon process monitoring + LaunchAgent/systemd integrity checks + chat platform connection audit + skills directory monitoring + credential exposure remediation |
| Default posture | Block for self-modification and external channel communication in any governed context; Approval Required for all other actions regardless of sensitivity tier |

**Class D criteria — all four required:**

1. **Daemon persistence** — runs 24/7 via LaunchAgent/systemd, not on user demand
2. **Proactive/scheduled execution** — can initiate agent turns without real-time user input (cron, heartbeat, webhook)
3. **External communication channels** — accepts prompts from external platforms (messaging apps, email, webhooks) beyond local terminal/IDE
4. **Self-modification** — writes/modifies own skill or plugin files that alter its capability set at runtime

### 5.2 Classification Resolution Logic

Classification is derived from multi-signal evidence across five dimensions:

1. **Execution capability** — assistive vs local inference vs autonomous command execution
2. **Action surface** — read/write/exec/network/privilege
3. **Autonomy level** — suggestion-only vs tool-calling loop
4. **Scope of impact** — single file vs repo-wide/system-wide
5. **Context sensitivity** — asset tier, identity trust tier, endpoint posture

**Rules:**
- If signals indicate multiple classes, assign **highest-risk applicable class**.
- If class confidence is low, apply conservative controls with lower-impact enforcement until confidence improves.
- Class assignment must include reason codes for analyst traceability.

### 5.3 Confidence-Coupled Decision Matrix

| Class | Confidence | Sensitivity | Decision |
|---|---|---|---|
| A | Low | Low | Detect |
| A | Medium | Medium | Warn |
| A | High | High | Approval Required / Block by policy |
| B | Medium | Medium | Warn + model/source verification |
| B | High | High | Approval Required |
| B | High | Restricted context violation | Block |
| C | Medium | Sensitive action | Approval Required |
| C | High | Disallowed command/scope | Block |
| C | Any | Repeated warning bypass | Block escalation |
| D | Any | R1 | Warn (minimum — no off-state means no "safe" baseline) |
| D | Medium+ | R2+ | Approval Required |
| D | High | R3+ | Block |
| D | Any | Self-modification or external channel communication | Block |

---

## 6. Enforcement Ladder

*Source: INIT-24*

The enforcement ladder is the deterministic decision spine converting detection signals into safe, explainable controls.

### 6.1 Enforcement States

| State | Purpose | Trigger Conditions | Required Output |
|---|---|---|---|
| **0 — Observe** | Internal pre-state: collect and normalize telemetry | All raw events | Enriched event candidate |
| **1 — Detect** | Record and monitor, no user disruption | Low confidence, low sensitivity, no policy violation | Event with class, confidence, context |
| **2 — Warn** | Notify user, create policy awareness | Medium confidence, policy drift, non-trivial risk | Warning reason, remediation guidance, ack marker |
| **3 — Approval Required** | Hold action pending authorized decision | Sensitive assets, privilege-impacting ops, medium/high confidence | Approval ticket with scope + expiration + approver |
| **4 — Block** | Deny action to enforce policy boundary | High-confidence prohibited behavior, repeated bypass, explicit deny | Deny reason, evidence trace, incident routing metadata |

### 6.2 Decision Inputs

| Dimension | Values |
|---|---|
| **Detection Confidence** | Low (<0.45), Medium (0.45–0.74), High (≥0.75) |
| **Asset Sensitivity** | Tier 0 (non-sensitive) → Tier 3 (crown-jewel/regulated) |
| **Actor Trust** | T0 (unknown) → T3 (privileged/admin) |
| **Action Risk** | R1 (read-only) → R4 (privileged/prohibited) |
| **Session History** | Prior warnings, active exceptions, repeat violations |

### 6.3 Deterministic Escalation Rules

| # | Condition | Decision |
|---|---|---|
| 1 | Low confidence + Tier 0/1 + R1 | Detect |
| 2 | Medium confidence + Tier 1/2 + R2 | Warn |
| 3 | Medium confidence + Tier 2/3 + R3 | Approval Required |
| 4 | High confidence + disallowed R4 | Block |
| 5 | Any confidence + explicit deny + Tier 3 | Block |
| 6 | Repeated Warn in same session (N threshold) | Step-up to Approval Required |
| 7 | Approval denied + retry same action | Block |
| D1 | Class D + any confidence + R3+ action | Block |
| D2 | Class D + medium+ confidence + R2 action | Approval Required |
| D3 | Class D + any confidence + R1 action | Warn (floor — no safe baseline exists for always-on agents) |

Rules D1–D3 take precedence over general rules 1–7 when `tool_class == "D"`. Each rule has a stable `rule_id`, version, and explainability payload.

#### Rule ID Catalog

The collector policy engine (`engine/policy.py`) assigns the following stable `rule_id` values. The first column maps each ID back to the numbered rules above.

| Rule ID | Maps to | Condition | Decision |
|---|---|---|---|
| ENFORCE-001 | Rule 1 | Low confidence + Tier 0/1 + R1 | detect |
| ENFORCE-002 | Rule 2 | Medium confidence + Tier 1+ + R2+ | warn |
| ENFORCE-003 | Rule 3 | Medium confidence + Tier 2+ + R3+ | approval_required |
| ENFORCE-004 | Rule 4 | High confidence + R4 | block |
| ENFORCE-005 | Rule 5 | Explicit deny + Tier 3 | block |
| ENFORCE-006 | (new) | Class C + Medium/High confidence + R3+ | approval_required |
| ENFORCE-D01 | Rule D1 | Class D + R3+ action | block |
| ENFORCE-D02 | Rule D2 | Class D + Medium/High confidence + R2 | approval_required |
| ENFORCE-D03 | Rule D3 | Class D (any) | warn |
| ENFORCE-001-F | Fallback | Low confidence, no specific rule match | detect |
| ENFORCE-002-F | Fallback | Medium/High confidence, no specific rule match | warn |
| ENFORCE-003-F | Fallback | High confidence + R3+ action, no specific rule match | approval_required |

**Overlay rules** (evaluated after base rules; can only escalate, never downgrade):

| Rule ID | Condition | Decision |
|---|---|---|
| NET-001 | Class C/D + unknown outbound connections | approval_required |
| NET-002 | Class C/D + unknown outbound + high volume (>=3) | block |
| ISO-001 | Class C + not running inside a container | block |

NET rules require a `NetworkContext` with allowlist-checked connections. ISO-001 uses `engine/container.py` to detect Docker/OCI containerization.

### 6.4 Session-Level Escalation

The ladder is stateful within session context:
- First medium-risk event → Warn
- Repeated medium-risk events → Approval Required
- Repeated denied attempts → Block + incident flag

**Current implementation:** `evaluate_policy()` accepts `prior_violations` (count of recent warnings) and escalates `warn` to `approval_required` when violations exceed 2. Actor trust tier T0 (unknown) escalates `detect` to `warn`. Full session-history persistence is planned for M3.

### 6.5 Explainability Contract

Every decision emits: `decision_state`, `rule_id`, `rule_version`, top contributing signals, penalties/uncertainty notes, target asset + action summary, actor context snapshot, and evidence IDs.

---

## 7. Risky Action Controls

*Source: INIT-25*

These are the execution guardrails sitting between AI-generated intent and real-world side effects. Detection alone does not prevent harm.

### 7.1 Action Risk Taxonomy

| Class | Description | Examples | Default Posture |
|---|---|---|---|
| **R1** | Low-impact read-only | Non-sensitive file reads, metadata lookups | Detect/Warn |
| **R2** | Scoped write/modify | Edits in approved paths, non-privileged config changes | Warn / Approval Required in sensitive context |
| **R3** | Broad or boundary-crossing | High fan-out writes, external uploads, cross-repo mutations | Approval Required; Block when denied |
| **R4** | Privileged/destructive/prohibited | Privilege escalation, credential access, protected path writes, disallowed commands | Block unless explicit time-bound exception |

### 7.2 Control Domains

#### A) Shell / Command Controls
- Command allow/deny matrix by risk class
- Privilege-aware gating (`sudo`, package install, service control)
- Sequence-aware checks (not just single command regex)
- High-risk command step-up approval

#### B) Filesystem Controls
- Protected path denylist (secrets, keys, system configs, regulated data)
- Path-scoped write allowlists by project/team
- File fan-out thresholds triggering escalation
- Overwrite-risk checks for critical files

#### C) Network / Egress Controls
- Destination allowlist by environment and tool class
- Egress gating for sensitive sessions
- Upload/path-aware transfer restrictions
- Proxy-aware identity checks

#### D) Repository / SDLC Controls
- Protected branch guardrails
- Mandatory PR/review gates for high-impact AI diffs
- Commit policy checks (identity/signature)
- Churn-based controls (LOC/files/components thresholds)

### 7.3 Contextual Gating Logic

Action class determines baseline control. Context can only **escalate or narrow** within policy bounds. Explicit deny always wins.

Context inputs: confidence score, asset sensitivity, actor trust tier, endpoint posture, exception state, session history.

---

## 8. Severity Taxonomy

*Source: INIT-38*

Severity maps agentic events to operational urgency, enforcement posture, and response SLAs.

### 8.1 Severity Levels

| Level | Definition | Example Triggers | Response Expectation |
|---|---|---|---|
| **S0 — Info** | Benign or low-confidence, no immediate risk | First-seen tool in non-sensitive env | Log and monitor |
| **S1 — Low** | Minor drift, limited impact scope | Medium-confidence use in low-sensitivity repo | Warning, routine review |
| **S2 — Medium** | Meaningful risk signal requiring analyst attention | Risky action in business-sensitive context; repeated warnings | Triage same business day |
| **S3 — High** | High-confidence risky behavior affecting sensitive assets | Unauthorized broad writes in protected repo; disallowed command execution | Rapid triage (hours), containment |
| **S4 — Critical** | Confirmed/near-certain severe breach with high impact | Prohibited privileged execution; high-confidence exfiltration path | Immediate incident handling, leadership notification |

### 8.2 Severity Determination Inputs

Severity is computed from weighted factors (never single-dimension):
1. Action risk class (R1–R4)
2. Asset sensitivity tier (Tier 0–3)
3. Detection confidence
4. Actor trust posture
5. Policy decision outcome
6. Recurrence pattern
7. Evidence integrity quality

**Hard floors:** Explicit-deny policy hits in Tier 3 contexts cannot score below S3.

### 8.3 Severity-to-SLA Mapping

| Severity | Analyst SLA | Reporting Tier |
|---|---|---|
| S0 | Backlog/periodic review | Aggregate trend |
| S1 | Routine queue | Weekly posture summary |
| S2 | Same business day | Operational review queue |
| S3 | Rapid (hours) | Incident candidate + management visibility |
| S4 | Immediate | Executive + incident command |

### 8.4 Escalation and Recurrence

- Repeated S1/S2 in same session/actor context → auto-escalate severity
- Repeated denied attempts → severity step-up + incident flag
- Recurrence windows configurable (rolling 24h/7d)
- Events allowed by exception still require severity scoring; scope exceedance escalates to S2+

---

## 9. Audit Schema and Event Model

*Sources: INIT-26, INIT-39*

The canonical event schema unifies detection, policy, enforcement, and audit data across all tools and environments.

### 9.1 Canonical Event Envelope

```
event {
  event_id:         UUID
  event_type:       enum (detection.observed | attribution.updated | policy.evaluated |
                          enforcement.applied | approval.requested | approval.resolved |
                          exception.lifecycle | evidence.linked | incident.flagged)
  event_version:    semver
  observed_at:      RFC3339
  ingested_at:      RFC3339
  session_id:       string
  trace_id:         string
  parent_event_id:  UUID (nullable)

  actor {
    id:                   string
    type:                 enum (human | service | automation)
    trust_tier:           enum (T0–T3)
    identity_confidence:  float [0,1]
    org_context:          enum (org | personal | unknown)
  }

  endpoint {
    id:       string
    os:       string
    posture:  enum (managed | unmanaged)
  }

  tool {
    name:                    string (nullable)
    class:                   enum (A | B | C)
    version:                 string (nullable)
    attribution_confidence:  float [0,1]
    attribution_sources:     array (process | file | network | identity | behavior)
  }

  action {
    type:        enum (read | write | exec | network | repo | privileged)
    risk_class:  enum (R1 | R2 | R3 | R4)
    summary:     string
    raw_ref:     string (pointer, not payload)
  }

  target {
    type:              enum (path | repo | host | destination | resource)
    id:                string
    scope:             string
    sensitivity_tier:  enum (Tier0–Tier3)
  }

  policy {
    decision_state:      enum (detect | warn | approval_required | block)
    rule_id:             string
    rule_version:        string
    reason_codes:        array[string]
    decision_confidence: float [0,1]
  }

  approval {
    id:        string (nullable)
    scope_id:  string (nullable)
  }

  exception {
    id:      string (nullable)
    status:  enum (nullable)
  }

  evidence {
    ids:              array[string]
    integrity_status: enum (valid | failed | pending)
    hash_refs:        array[string]
  }

  outcome {
    enforcement_result:  enum (allowed | held | denied)
    incident_flag:       boolean
    incident_id:         string (nullable)
  }

  severity {
    level:  enum (S0 | S1 | S2 | S3 | S4)
  }
}
```

### 9.2 Evidence Object Model

Evidence objects are linked, not embedded. Each contains:
- `evidence_id`, `evidence_type` (process_tree | file_diff | netflow | policy_eval | approval_record)
- `captured_at`, `storage_uri`, `hash`
- `redaction_level`, `chain_of_custody`

### 9.3 Validation Rules

- Required fields enforced per event type
- Strict enums for all decision-critical semantics
- Confidence range constraints [0,1]
- Rule/evidence linkage required for policy events
- Missing required fields → schema conformance failure

### 9.4 Retention Tiers

| Tier | Purpose | Duration |
|---|---|---|
| Hot | SOC triage, real-time dashboards | Days–weeks |
| Warm | Investigations, trend analysis | Weeks–months |
| Cold | Compliance archive, forensic recall | Months–years (policy-defined) |

---

## 10. Exception Workflow

*Source: INIT-27*

Exceptions are controlled risk instruments, not policy bypasses. Poorly designed exceptions are the primary attack path against any governance system.

### 10.1 Exception Object Model

| Field Group | Required Fields |
|---|---|
| **Identity** | `exception_id`, `requester_id`, `approver_id`, `owner_team` |
| **Scope** | `tool_class`, `actions_allowed`, `target_scope`, `environment_scope` |
| **Time Bounds** | `effective_from`, `expires_at`, `max_duration_policy` |
| **Justification** | `business_justification`, `risk_assessment`, `compensating_controls`, `residual_risk_statement` |
| **Governance** | `linked_policy_rule_ids[]`, `approval_ticket_id` |
| **State** | `status` (pending/active/expired/revoked/rejected) |

### 10.2 Lifecycle

```
Draft/Pending → Review → Active → Expired
                  ↓                  ↑
               Rejected         Revoked (immediate)
```

- **Active** exceptions generate scoped tokens referenced at enforcement time
- **Expired** exceptions auto-revert to baseline policy
- **Revoked** exceptions emit high-priority events for SOC visibility

### 10.3 Approval Tiers

| Risk Level | Approval Requirement |
|---|---|
| Low-risk scope | Single approver (team lead / security delegate) |
| Medium-risk scope | Security + service owner |
| High-risk (Class C / privileged / sensitive) | Dual approval required |

### 10.4 Anti-Abuse Protections

- No wildcard exceptions for Class C autonomous actions
- No open-ended destination/path scopes
- No infinite duration
- No transitive inheritance across repos/hosts/environments
- Repeated denied retries trigger escalation
- Stale exceptions auto-expire

### 10.5 Runtime Enforcement

1. Baseline policy evaluates first
2. Exception lookup checks exact-scope match
3. If matched and valid → decision can downgrade from Block/Approval to allowed
4. If unmatched/expired → baseline decision applies
5. Every exception-mediated allow emits: `exception_id`, matched scope, reason code, evidence references

---

## 11. Tooling and Integration Map

This section maps playbook components to the infrastructure and tools required for implementation.

### 11.1 Telemetry Collection Layer

| Telemetry Layer | Collection Mechanism | Platform Notes |
|---|---|---|
| Process / Execution | EDR agent process telemetry, OS audit subsystem (auditd/ETW/ESF), sysmon-equivalent | macOS: Endpoint Security Framework; Windows: ETW + Sysmon; Linux: auditd + eBPF |
| File / Artifact | File integrity monitoring (FIM), EDR file event stream, periodic artifact sweeps | Schedule artifact inventory scans for model storage dirs; hash-based change detection |
| Network | EDR network telemetry, host-based firewall logs, DNS/SNI capture | Localhost traffic requires host-level capture (invisible to CASB/SWG); process-to-socket correlation critical |
| Identity / Access | IdP integration, endpoint management agent, OS session telemetry | Map endpoint user → org identity → account type; requires MDM or identity agent |
| Behavior | Derived from correlated process + file + network temporal sequences | Built in attribution engine, not a raw telemetry source |

### 11.2 Attribution and Policy Engine

| Component | Function | Integration Points |
|---|---|---|
| **Attribution Engine** | Multi-signal correlation, tool class assignment, confidence scoring | Consumes all 5 telemetry layers; emits canonical events |
| **Policy Engine** | Class→controls mapping, enforcement ladder evaluation, exception resolution | Consumes attributed events + policy config; emits decisions |
| **Rule Store** | Versioned policy rules with deterministic IDs | Policy engine reads; change management workflow writes |
| **Exception Store** | Active/expired/revoked exception state | Policy engine reads at enforcement time; exception workflow writes |

### 11.3 Enforcement and Output

| Component | Function | Downstream Consumers |
|---|---|---|
| **Enforcement Actuator** | Executes detect/warn/approval/block actions | User-facing notifications, agent controls |
| **Audit Pipeline** | Canonical event normalization, evidence linkage, immutable storage | SIEM export, compliance archive, investigation tools |
| **Severity Router** | Computes severity, routes to appropriate SLA/incident path | SOC console, incident management, paging |
| **Reporting Engine** | Coverage heatmaps, decision quality, trend analysis | Analyst dashboards, buyer-facing reports |

### 11.4 SIEM / SOC Integration Points

| Data Flow | Format | Notes |
|---|---|---|
| Events → SIEM | Canonical event schema (JSON) via syslog/API push | Include all policy decision fields for correlation |
| Alerts → SOC | Severity-routed alerts with evidence links | S2+ events should include one-click evidence drill-down |
| Dashboards | Aggregated metrics by tool class, severity, decision state | Pre-built views for: tool inventory, policy efficacy, exception posture |

### 11.5 Cross-Platform Collector Architecture

The endpoint collector uses a platform abstraction layer (`collector/compat/`) that decouples scanner logic from OS-specific system calls. This enables the same scanner codebase to run on macOS, Linux, and Windows without per-scanner platform forks.

**Abstraction modules:**

| Module | Replaces | Backend |
|---|---|---|
| `compat/processes.py` | `pgrep`, `ps` | `psutil.process_iter()`, `psutil.Process()` |
| `compat/network.py` | `lsof`, `netstat` | `psutil.net_connections()` |
| `compat/services.py` | `brew services`, `systemctl`, `launchctl` | macOS: `launchctl`/`brew`; Linux: `systemctl`; Windows: `psutil.win_service_get()` |
| `compat/identity.py` | `id`, `security find-generic-password`, `codesign` | macOS: `pwd`/`security`/`codesign`; Linux: `pwd`/`secret-tool`; Windows: `net user`/`cmdkey`/PowerShell `Get-AuthenticodeSignature` |
| `compat/paths.py` | Hardcoded macOS paths | Platform-dispatched path registry (macOS/Linux/Windows) for each tool's install, config, data, extension, and log directories |

**Platform coverage (psutil 7.x):**

| Platform | Process enum | Network connections | Service detection | Code signature | Credential store |
|---|---|---|---|---|---|
| macOS | psutil | psutil | launchctl + brew | codesign CLI | security CLI |
| Linux | psutil | psutil | systemctl | N/A | secret-tool |
| Windows 11 | psutil | psutil | psutil (SCM) | PowerShell | cmdkey |
| Windows Server 2019/2022/2025 | psutil | psutil | psutil (SCM) | PowerShell | cmdkey |

**Privilege considerations:**

- **Non-admin:** Process enumeration works but falls back to a slower code path on Windows (~10x slower). Network PID mapping may be incomplete. Sufficient for developer-workstation scanning where the agent runs as the same user as the tools it detects.
- **Elevated / MDM-deployed:** Full-speed process enumeration, complete PID-to-connection mapping, cross-user process visibility. MDM deployment (Intune, JAMF, SCCM) runs the installer as SYSTEM/root, and the resulting service inherits elevation — the performance penalty disappears.
- **Recommendation:** Require elevation for production deployments. This is consistent with the agent's role as a security monitoring tool.

**Migrated scanners (proof of concept):** Cursor, Ollama, GitHub Copilot. Remaining 8 scanners (Claude Code, Aider, GPT-Pilot, Cline, Continue, LM Studio, Open Interpreter, OpenClaw) still use direct subprocess calls and will be migrated in a follow-on pass.

### 11.6 Synthetic Scanner Test Infrastructure

To validate scanner detection logic without requiring the target tools to be installed or running, a synthetic fixture test suite provides deterministic, CI-friendly coverage across all five detection layers.

**Architecture:**

| Component | File | Purpose |
|---|---|---|
| File fixtures | `collector/tests/fixtures/file_fixtures.py` | Creates realistic file/directory footprints in a temp directory for each tool (config files, extension manifests, model files, task histories, etc.) |
| Canned responses | `collector/tests/fixtures/canned_responses.py` | Pre-built `CompletedProcess` objects that mock `_run_cmd` output for `pgrep`, `ps`, `lsof`, `pip show`, and other subprocess calls |
| Dispatcher | `make_dispatcher()` in `canned_responses.py` | Routes mocked `_run_cmd` calls to the correct canned response by matching command argument tuples |
| Per-scanner tests | `collector/tests/test_scanner_<tool>.py` | Integration tests that combine file fixtures (real temp files) with mocked subprocesses to exercise each scanner end-to-end |

**Patching strategy:** Each test patches the scanner module's `HOME` constant to point to a `tempfile.TemporaryDirectory`, so file-layer checks hit real (fixture) files while process/network checks use mocked output. For LM Studio, `APP_PATH` is also patched since it references an absolute `/Applications/` path. Environment variables (`OPENAI_API_KEY`, etc.) are patched out in clean-system tests to prevent host-environment leakage.

**Scanner coverage (22 tests across 5 scanners):**

| Scanner | Class | Scenarios | Key validations |
|---|---|---|---|
| Aider | C | Clean, installed-not-running, fully-active, git-commit-detection | Prompt-edit-commit loop (child process tree), `.aider*` artifact aging, git commit attribution pattern matching |
| LM Studio | B | Clean, installed-not-running, fully-active, server-without-API | App bundle detection, model file enumeration (`.gguf`), `:1234` listener, `/v1/models` API response parsing |
| Continue | A | Clean, installed, approved-backend-active, unapproved-ollama, mixed-backends | `config.json` backend parsing, unapproved provider detection (`ollama`, `lmstudio`), evasion boost, extension manifest in `.cursor/extensions/` |
| GPT-Pilot | C | Clean, state-dirs-only, generation-loop-active, high-file-churn | `.gpt-pilot/` state directory scanning, child process tree (node + python children), high file churn (>20 files in 1 hour) |
| Cline | A/C | Clean, extension-installed, task-history-class-A, tool-calls-class-C, write-ops-class-C-R3 | Dynamic class escalation (A→C) based on `ui_messages.json` content, `tool_use` vs `write_to_file`/`execute_command` type detection, `globalStorage` task directory inspection |

**What this validates vs. what it does not:**

| Validated by synthetic tests | Requires live lab runs |
|---|---|
| File-layer artifact path detection (config files, extensions, models, state dirs) | Actual tool process behavior under real workloads |
| Process-layer output parsing (PID extraction, child process identification, cmdline regex matching) | Real process tree structures and timing |
| Network-layer output parsing (lsof LISTEN/ESTABLISHED detection, port matching) | Actual network traffic patterns and connection timing |
| Identity-layer logic (user extraction, API key environment detection) | Real account/credential states |
| Behavior-layer logic (file churn counting, artifact recency, tool-call classification) | Real behavioral sequences and temporal patterns |
| Confidence penalty application | Calibrated penalty thresholds against real data |
| Class escalation logic (Cline A→C, Continue unapproved backend) | Edge cases in class boundary behavior |
| Risk and action assignment (`action_risk`, `action_type`) | Policy decision accuracy under production conditions |

**Running:**

```
PYTHONPATH=collector python -m pytest collector/tests/test_scanner_*.py -v
```

---

## 12. Lab Validation Runs

This section provides the framework for empirical validation. Each tool profile defines minimum positive and adversarial scenarios; this section tracks execution status and findings.

### 12.1 Validation Matrix (Minimum Per Tool)

| Tool | Positive Scenarios (≥3) | Evasion Scenarios (≥2) | Status |
|---|---|---|---|
| Claude Code | Standard CLI, multi-file refactor + git, shell tool usage | Renamed binary, proxy-routed API | `IN PROGRESS` (2/3 positive, 1/2 evasion) |
| Cursor | Standard editing, AI-assisted refactor, terminal workflow | Wrapped launch path, proxy attribution | `IN PROGRESS` (1/3 positive) |
| Copilot | Org account normal use, chat-assisted edit, full-layer session | Personal account on managed endpoint, proxy route | `IN PROGRESS` (1/3 positive — unauthenticated baseline) |
| Ollama | Approved model pull+run, inference session, local API automation | Custom port/container, side-loaded models | `IN PROGRESS` (1/3 positive) |
| LM Studio | Approved model load, model switch + prompts, identity-mapped use | Non-default path + renamed artifacts, non-default port | `SYNTHETIC VALIDATED` (4 scenarios) |
| Continue | Approved backend workflow, config-defined backend switch, multi-file edit | Forked config to unsanctioned endpoint, proxy gateway | `SYNTHETIC VALIDATED` (5 scenarios) |
| Open Interpreter | Benign command session, multi-step automation, policy-compliant repo task | Wrapped launch, ephemeral venv/container | `IN PROGRESS` (1/3 positive) |
| Aider | Single-module change + PR, multi-file refactor, formatting/test session | Alias/wrapper invocation, devcontainer execution | `SYNTHETIC VALIDATED` (4 scenarios) |
| GPT-Pilot | Greenfield scaffold, iterative gen+test loop, controlled module expansion | Forked launcher, containerized execution | `SYNTHETIC VALIDATED` (4 scenarios) |
| Cline | Approved backend + code-assist, multi-file edit, controlled tool-calling | Forked extension build, shared proxy route | `SYNTHETIC VALIDATED` (5 scenarios) |
| OpenClaw | Standard install + onboard + agentic task + skill creation, multi-channel session, proactive/scheduled execution, **local LLM backend (OC-POS-05)** | Renamed binary, custom port, containerized gateway, local-only model backend | `IN PROGRESS` (2/3 positive) |
| Claude Cowork | **Standard install + launch + session analysis + teardown (CW-POS-01)**, MCP connector agentic task, scheduled task exercise | Non-standard install, VPN-routed API, DXT extension modification | `IN PROGRESS` (1/3 positive) |

### 12.2 Lab Run Evidence Template

Each completed run must produce:

```
Run ID:              [unique identifier]
Date:                [execution date]
Tool:                [tool name + version]
Scenario ID:         [from validation matrix]
Environment:         [OS, endpoint posture, network topology]
Scenario Type:       [positive | evasion | governance stress]

Signal Observations:
  Process:           [observed / not observed — details]
  File/Artifact:     [observed / not observed — details]
  Network:           [observed / not observed — details]
  Identity:          [observed / not observed — details]
  Behavior:          [observed / not observed — details]

Confidence Result:   [score + rationale]
Policy Decision:     [detect/warn/approval/block + rule_id]
Evidence Links:      [references to collected artifacts]
Pass/Fail:           [pass | conditional pass | fail]
Residual Risk:       [statement of remaining coverage gaps]
```

### 12.3 Priority Ordering for First Lab Sprint

1. **Claude Code** (Class C, agentic mode) — highest risk, reference implementation for signal map
2. **Open Interpreter** (Class C, autonomous executor) — validates command-chain detection
3. **Ollama** (Class B, local runtime) — validates perimeter-blind-spot detection
4. **Cursor** (Class A→C, IDE agent) — validates class escalation logic
5. Remaining tools in descending risk-class order

### 12.4 Methodology Lessons

**From LAB-RUN-001 (Claude Code):**

1. **Sub-second process monitoring required for agentic scenarios.** Polling `pstree` at 2-second intervals missed transient child processes (shell → python → pytest). Future runs must use macOS ESF (`eslogger exec`) or a ≤500ms polling loop for Phase 3 captures.
2. **`lsof` polling cannot attribute short-lived HTTPS to a specific PID.** Claude Code's API calls complete between 2-second polling intervals. Network-layer confidence for CLI tools requires continuous telemetry (EDR agent, `tcpdump` with process correlation, or ESF network events).
3. **Terminal session recording via `script` is essential.** LAB-RUN-001 did not capture the interactive terminal session. The agentic loop sequence (prompt → permission dialog → execution → result) was inferred from artifacts, not directly observed. Future runs must start `script` before launching the tool.
4. **Artifact-based confirmation is a valid fallback** for child process detection. `.pytest_cache/`, `.pyc` files, and build artifacts prove shell execution even when the process itself was too transient to capture.

**From LAB-RUN-003 (Ollama):**

5. **Network detection difficulty inverts between Class B and Class C tools.** Claude Code makes short-lived HTTPS bursts that evade polling-based capture. Ollama's persistent localhost listener on `:11434` is trivially detectable via `lsof` at any polling interval. Network-layer confidence assumptions should be calibrated per tool class.
6. **`ollama run` is TTY-interactive and does not capture well non-interactively.** The CLI inference command expects an interactive terminal. For lab capture, use the `/api/generate` HTTP endpoint with `"stream": false` as the primary inference evidence source.
7. **Client-server process architecture requires dual detection.** Ollama's CLI commands (`ollama run`, `ollama pull`) are HTTP clients of the daemon, not child processes. Detection must monitor both the long-lived daemon *and* transient CLI invocations independently — parent-child chain detection will miss the relationship.
8. **Identity layer has an inherent ceiling for Class B local runtimes.** Ollama has no account system, OAuth, or API keys. Identity is limited to OS process ownership. This is an architectural characteristic, not an instrumentation gap. Layer weights should be adjusted accordingly for Class B tools.
9. **`~/.ollama/` creation timing mirrors Claude Code.** Both tools create their data directories on first *run*, not during install. Detection rules must not treat absence of data directories after install as evidence of tool absence.

**From LAB-RUN-006 (Open Interpreter):**

10. **Class C confidence profiles are NOT generalizable across tools.** Open Interpreter (0.525) scored materially lower than Claude Code (0.71) despite both being Class C. The detection profiles are inverted: Claude Code is file-anchored (0.95 file layer); Open Interpreter is behavior-anchored (0.85 behavior layer). Per-tool weight calibration within the same class is empirically justified.
11. **Generic Python process names require deeper inspection than named binaries.** Open Interpreter appears as `python3` in `ps`, not as `interpreter`. Detection rules matching binary names (like `node.*claude` for Claude Code) will not work. Must match Python processes with module paths in arguments or link to venv entrypoints.
12. **Jupyter/IPyKernel mediation adds process chain indirection.** Open Interpreter executes code through a Jupyter kernel subprocess. The child chain is: python3 (interpreter) → python3 (ipykernel_launcher) → bash → commands. Parent-child lineage detection must account for this extra layer.
13. **Ephemeral session models limit post-hoc detection.** Open Interpreter v0.4.3 creates ZERO persistent state outside the virtualenv. No `~/.config/open-interpreter/`, no session logs. Deleting the venv eliminates nearly all forensic evidence. File-layer detection is fundamentally weaker for tools with ephemeral state.
14. **Virtualenv install locations are arbitrary and unpredictable.** Unlike `~/.claude/` (fixed) or `/opt/homebrew/bin/ollama` (well-known), venvs can be created anywhere. Artifact-sweep detection must search for `interpreter` package across all Python environments.
15. **`auto_run=True` flag is the highest-risk configuration signal.** When set, Open Interpreter executes ALL generated code without human confirmation. Detection of this flag in process arguments is itself a governance-relevant signal.

**From LAB-RUN-004 (Cursor):**

10. **Multi-process Electron architecture is a governance advantage.** Cursor's labeled extension-host types (`user`, `retrieval-always-local`, `agent-exec`) create a natural process-level indicator of tool class. The `agent-exec` host directly maps to Class C — no other tool provides a process signal that maps this cleanly to governance class.
11. **High confidence achievable without sudo/EDR.** Cursor scored 0.79 (High) using only non-privileged tools (`ps`, `lsof`, `pstree`, file listing). This is the first tool to reach High confidence without elevated access. Multi-process architecture and persistent network connections are detectable with standard user-level tools.
12. **Cursor account state stored in Electron user-data-dir, not `~/.cursor/`.** The `--user-data-dir=/Users/<user>/Library/Application Support/Cursor` path (visible in process arguments) contains account/auth state. Detection must check both `~/.cursor/` and `~/Library/Application Support/Cursor/` for complete artifact coverage.
13. **Class A→C escalation is observable in real-time via process tree.** The presence of `extension-host (agent-exec)` with child `/bin/zsh` processes indicates active Class C behavior. This transitions are visible to any process monitoring system without needing to examine network or file artifacts.
14. **Git trailer attribution parallels across tools.** Cursor adds `Made-with: Cursor` to commits; Claude Code adds `Co-Authored-By`. Both are one-way signals. A unified evasion test protocol should be developed for trailer suppression across all tools.

**From LAB-RUN-005 (GitHub Copilot):**

15. **IDE extension process attribution requires cross-layer correlation.** VS Code's extension host process (`Code Helper (Plugin)`) hosts ALL extensions in the same process context. Process-layer detection alone cannot attribute activity to Copilot specifically — it requires file-layer (extension directory check) or network-layer (Copilot endpoint traffic) correlation. This is a fundamental difference from standalone tools (Claude Code, Ollama) where the process IS the tool.
16. **Authentication state creates a bimodal detection profile for Class A tools.** Copilot's identity layer is the strongest governance signal when authenticated (~0.90) but the weakest when not (~0.40). This bimodal distribution differs fundamentally from Claude Code (identity always strong via OAuth) and Ollama (identity always weak, no accounts). Weight calibration for Class A tools should be context-dependent: higher identity weight for authenticated scenarios, lower for unauthenticated.
17. **VS Code telemetry contains rich device and session identifiers even without tool activation.** The `machineId` (SHA-256) and `devDeviceId` (UUID) persist across sessions and reinstalls. Combined with session UUIDs and A/B experiment flags, VS Code's telemetry provides robust device fingerprinting and Copilot feature-state detection without examining extension files.
18. **`chatEntitlement` vs `chatRegistered` fields distinguish installation from activation.** These telemetry fields enable three-state detection: not installed, installed-but-dormant, and active. The dormant state (installed but unauthenticated) is itself a governance finding — tool present on endpoint without active usage.
19. **VS Code's Network Service centralizes all connections in one attributable process.** Unlike Claude Code (connections from main process, ephemeral) or Ollama (daemon listener), VS Code routes all network I/O through a dedicated `Code Helper (Network)` process. This makes process-to-socket attribution trivial at any polling interval — similar to Ollama's persistent listener but for outbound HTTPS.
20. **Copilot's agent mode capabilities are gated behind authentication and feature flags.** Experiment flags (`edit_mode_hidden`, `use-responses-api`) in VS Code 1.109.5 indicate agent/edit mode exists as a capability. When exercised, this would represent a Class A→C escalation path similar to Cursor. Classification should be re-evaluated when agent mode is validated (CP-POS-03).

**From LAB-RUN-007 (OpenClaw):**

21. **LaunchAgent plist is a credential store and detection goldmine.** OpenClaw's `ai.openclaw.gateway.plist` embeds API keys, external service credentials (JIRA), gateway tokens, and PATH configuration as environment variables. The plist is world-readable (mode 644). Detection should treat LaunchAgent plists as high-value identity and configuration artifacts. Any tool that installs a LaunchAgent may embed credentials.
22. **`KeepAlive: true` + `RunAtLoad: true` is the strongest persistence of any profiled tool.** This combination means the daemon auto-starts on login AND auto-restarts on kill. `launchctl unload` stops the daemon, but `kill` alone does not — launchd respawns it. Detection must account for always-on daemons that survive process termination.
23. **Self-modification requires no approval gate.** OpenClaw's agent created a new skill file with a single prompt. No human confirmation was requested. The skill watcher auto-reloads changes. Governance must monitor writes to `~/.openclaw/workspace/skills/` as a high-risk behavioral signal.
24. **`openclaw status` is the richest single-command diagnostic of any tool.** Reveals gateway state, channel connections (with linked phone numbers), session inventory, model assignments, token usage, security audit findings, heartbeat config, and memory state. Recommend periodic `openclaw status` capture for governance monitoring.
25. **OpenClaw CLI is a thin client — all intelligence runs in the daemon.** `openclaw agent --agent main --message "..."` sends a message to the gateway via WebSocket. The daemon handles the agent turn. Detection should focus on the daemon process, not the transient CLI invocations — same client-server pattern as Ollama.
26. **Config backup chain enables forensic reconstruction.** `openclaw.json.bak` through `.bak.4` (5 generations) preserve configuration history. Diffs reveal when channels were added, models changed, or security settings modified. Useful for incident timeline construction.
27. **Class D taxonomy is now formalized with OpenClaw as the reference implementation.** OpenClaw satisfies all four Class D criteria: daemon persistence (`KeepAlive + RunAtLoad`), proactive/scheduled execution (cron/heartbeat infrastructure), external communication channels (WhatsApp/Telegram/Slack), and self-modification (agent writes and hot-reloads its own skills). See Section 5.1 for the full Class D definition and policy posture.

**From LAB-RUN-013 (OpenClaw — local LLM variant):**

28. **Model capability directly affects behavioral detection confidence.** The 0.8B Qwen 3.5 model could not perform tool use, shell execution, or self-modification. Behavioral IOCs that depend on agentic execution are only detectable when the model is capable enough. Detection must not rely solely on observed behavior — infrastructure IOCs (process, file, persistence) are model-independent and should be weighted as primary detection anchors.
29. **Local LLM eliminates outbound model API traffic but NOT all outbound connections.** With Ollama as the model backend, inference traffic stayed on `127.0.0.1:11434`. However, the OpenClaw gateway still maintained an outbound `:443` connection (telemetry, update checks, or channel keepalive). Network detection cannot assume "local model = zero outbound traffic."
30. **OpenClaw + Ollama co-residency creates a symbiotic detection pattern.** When OpenClaw uses Ollama, both tools run simultaneously: gateway on `:18789`, Ollama on `:11434`, with loopback connections between them. Detection of both together indicates a local autonomous agent configuration — a cross-tool IOC not seen with any other tool pair.
31. **Model swap is a config-only change with no approval gate.** Changing from a cloud LLM to a local LLM (or vice versa) requires only editing `openclaw.json`. There is no audit trail beyond config backup files. A user could swap from a small, incapable model to a large, fully agentic model in seconds — behavioral risk is *latent*, not absent.
32. **OpenClaw's own security audit flags small models as governance-relevant.** `openclaw status` reported "CRITICAL: Small models require sandboxing and web tools disabled" for the 0.8B model. The tool's built-in security diagnostics can be leveraged as governance signals.
33. **A confidence floor for infrastructure-class tools prevents underscoring.** With a small model, OpenClaw's confidence dropped from 0.80 (High) to 0.725 (Medium) entirely due to the behavior layer. A confidence floor based on process + file layer strength (both ≥ 0.80) would prevent underscoring tools with capable infrastructure but temporarily incapable models.

**From Synthetic Fixture Tests (Aider, LM Studio, Continue, GPT-Pilot, Cline):**

34. **Synthetic fixtures can validate scanner parsing logic without tool installs.** For scanners that detect tools via file artifacts and subprocess output parsing, the detection logic can be tested deterministically by creating real files in temp directories (patching `HOME`) and mocking `_run_cmd` with canned subprocess output. This validated all five scanners for the 5 un-lab-run tools (Aider, GPT-Pilot, Cline, LM Studio, Continue) across 22 test scenarios without any tool installs, API keys, or GPU hardware. See Section 11.6 for architecture details.
35. **Scanners with unconditional identity signals cannot report `detected=False` on a clean system.** The Continue and Cline scanners call `getpass.getuser()` unconditionally, returning identity strength >= 0.25 regardless of whether the tool is present. This means `detected=True` even when no tool is installed — clean-system tests must assert on per-layer signal strengths rather than the `detected` flag. This is a design consideration for scanners that embed IDE extensions: they cannot distinguish "IDE running, extension absent" from "nothing running" at the identity layer alone.
36. **Canned network responses must be backend-aware for extension scanners.** The Continue scanner interprets connections to `:11434` (Ollama) or `:1234` (LM Studio) as evidence of unapproved local backends, independent of what `config.json` says. Canned response sets must match the intended scenario — an "approved backend active" scenario needs connections to cloud API endpoints (`:443`), not local model server ports. This subtlety was caught during test development.
37. **Dynamic class assignment requires scenario-specific fixture data.** Cline's class escalation from A to C depends on the content of `ui_messages.json` in the most recent task directory. Tests must construct fixture data that exercises both sides of the classification boundary: entries with `type: "say"` (Class A) vs `type: "tool_use"` or `type: "write_to_file"` (Class C). This validates that the scanner's parsing logic correctly maps message types to governance classes.

**From LAB-RUN-014 (Claude Cowork):**

38. **VM-based sandboxed execution is a fundamentally different threat model.** Claude Cowork runs a full Linux VM via Apple Virtualization framework (`com.apple.security.virtualization` entitlement). File operations happen inside the VM, not on the host. Detection must identify both the Electron app processes AND the `com.apple.Virtualization.VirtualMachine` XPC service. The VM process is the strongest single indicator that Cowork (not just Claude chat) is active.
39. **Cowork's split attack surface requires dual monitoring.** File operations are VM-isolated (sandboxed). However, DXT extensions (chrome-control, notes) and MCP connectors (Google Calendar, Indeed) operate on the host outside the VM. Governance must monitor both the VM-sandboxed session activity and the host-level DXT/MCP activity. This split is unique among profiled tools.
40. **Session JSON files are the richest single forensic artifact of any tool.** Each `local_*.json` file (110–114 KB) contains: account identity (name + email in cleartext), model selection, initial message, full system prompt (42 KB), MCP connector inventory, VM egress allowlist (22 domains), session UUIDs, and slash command inventory. A single file provides identity, capability, network boundary, and behavioral context.
41. **VM egress allowlist is a novel compliance-as-code artifact.** The `egressAllowedDomains` array in session JSON self-reports the VM's outbound network boundary. Monitoring changes to this allowlist across app versions would detect capability expansion. This is a governance signal where the tool itself declares its network constraints.
42. **"Soft proactive" execution bridges Class C and Class D.** Cowork's `schedule` skill creates recurring tasks with cron expressions, and `coworkScheduledTasksEnabled: true` enables them. However, scheduled tasks only run while the app is open — no daemon persistence. This represents a new capability category between Class C (user-triggered) and Class D (always-on). Classification framework should account for this intermediate state.
43. **10 GB passive footprint enables trivial disk-based detection.** The VM `rootfs.img` alone is 10 GB — orders of magnitude larger than any other tool's artifacts. Disk space monitoring or file system surveys will detect Cowork with near-zero false positive rate. The `vm_bundles/claudevm.bundle/` path is pathognomonic.

### 12.5 Lab Run Log

| Run ID | Date | Tool | Scenario | Result | Notes |
|---|---|---|---|---|---|
| LAB-RUN-001 | 2026-02-26 | Claude Code v2.1.59 | CC-POS-01: Standard CLI install + agentic task | **Conditional Pass** | Confidence: 0.71 (Medium). 9/12 IOCs confirmed. Network layer under-instrumented. 10 findings fed back to playbook. Full results: `LAB-RUN-001-RESULTS.md` |
| LAB-RUN-002 | 2026-02-26 | Claude Code v2.1.59 | CC-POS-02: Multi-module project + git + tests | **Pass** | All three RUN-001 gaps closed: (1) terminal session recorded via `script` (5,629 lines), (2) git IOC confirmed — `git init` + `git add` + `git commit` with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer, (3) child process chain captured at 500ms polling: `claude` → `/bin/zsh` → `bash` → python/git. 6 source files, 199 LOC, 16 tests. Full results: `LAB-RUN-002-RESULTS.md` |
| LAB-RUN-EVASION-001 | 2026-02-26 | Claude Code v2.1.59 | CC-EVA-01: Co-Authored-By trailer evasion | **Pass (6/6 vectors succeeded)** | Tested 6 evasion vectors against the `Co-Authored-By` git trailer: settings suppression, amend, rebase, commit-msg hook, filter-branch, global template hook. **All succeeded.** Key finding: trailer is a high-confidence *positive* signal but a zero-confidence *negative* signal. Most dangerous vector: `commit-msg` hook strips trailer before it enters the object store — zero forensic trace. Added evasion counter-indicators to Section 4.1. Full results: `LAB-RUN-EVASION-001-RESULTS.md` |
| LAB-RUN-003 | 2026-02-26 | Ollama v0.17.0 | OL-POS-01: Standard install + model pull + inference | **Conditional Pass** | First Class B tool validated. Confidence: 0.69 (Medium). 9/9 Section 4.4 IOCs confirmed. Key findings: (1) Ed25519 keypair on first `serve` is new file IOC, (2) localhost:11434 listener trivially attributable — inverts network difficulty vs Class C, (3) unauthenticated API is governance risk, (4) identity layer architecturally weak (no accounts/OAuth), (5) OCI-format model manifests enable provenance tracing, (6) client-server process model (CLI ≠ child of daemon). 10 findings fed back. Proposed Class B weight calibration (Identity 0.15→0.10, File 0.20→0.25, Network 0.15→0.20). Full results: `LAB-RUN-003-RESULTS.md` |
| LAB-RUN-006 | 2026-03-02 | Open Interpreter v0.4.3 | OI-POS-01: Standard venv install + agentic command execution | **Conditional Pass** | Second Class C tool validated. Confidence: 0.525 (Medium) — notably lower than Claude Code (0.71). 10/14 IOCs confirmed. Key findings: (1) Process name is generic `python3`, not `interpreter` — requires module-path matching, (2) uses Jupyter/IPyKernel for code execution (indirection layer), (3) ZERO persistent state outside virtualenv — ephemeral session model limits post-hoc forensics, (4) venv location arbitrary, (5) behavior layer is primary detection anchor (inverted from Claude Code), (6) `auto_run=True` eliminates all safety confirmations, (7) model provider configurable — network target not fixed, (8) package-install-then-execute chain (risk marker) confirmed. **Class C profiles are NOT generalizable** — tool-specific weight calibration needed. Proposed OI weights: Behavior 0.35, Process 0.25, File 0.15, Network 0.15, Identity 0.10. OpenAI quota exceeded during lab; Ollama local backend used as fallback. Full results: `LAB-RUN-006-RESULTS.md` |
| LAB-RUN-004 | 2026-03-02 | Cursor v2.5.26 | CUR-POS-01: Standard IDE session + AI edit + agentic task | **Pass** | First Class A→C tool validated. **First High confidence score: 0.79.** First tool to reach High without sudo/EDR. 9/9 Section 4.2 IOCs confirmed. Key findings: (1) `extension-host (agent-exec)` is binary Class C escalation indicator in process tree, (2) agent transcript JSONL files provide complete session forensics, (3) `ai-code-tracking.db` is centralized AI activity tracker, (4) persistent TLS connections PID-attributable (inverts Claude Code's network gap), (5) `Made-with: Cursor` git trailer (one-way signal), (6) identity state in Electron user-data-dir not `~/.cursor/`, (7) code signing provides cryptographic provenance. 10 findings fed back. Proposed Cursor weight calibration (Network 0.15→0.20, Identity 0.15→0.10). Full results: `LAB-RUN-004-RESULTS.md` |
| LAB-RUN-005 | 2026-03-02 | GitHub Copilot (github.copilot-chat v0.37.9) in VS Code 1.109.5 | CP-POS-01: Standard VS Code session + Copilot install + launch (unauthenticated) | **Conditional Pass** | **First Class A tool validated. Empirical data now exists for all three tool classes (A, B, C).** Confidence: 0.45 (Medium, barely) — depressed by unauthenticated scenario (projected ~0.74 with auth, ~0.80 with EDR). 4/11 IOCs confirmed, 2 partially observed, 5 not observed (all due to unauthenticated state). Key findings: (1) Extension installed as bundled `github.copilot-chat` (lowercase, single extension), (2) extension-host process shared by all extensions — requires cross-layer correlation, (3) VS Code `machineId` + `devDeviceId` provide persistent device identity, (4) `chatEntitlement`/`chatRegistered` distinguish installed/entitled/active states, (5) GitHub Authentication log records explicit auth state, (6) VS Code Network Service centralizes all connections in one attributable PID, (7) persistent HTTPS connections (not ephemeral like Claude Code), (8) A/B experiment flags enable Copilot version fingerprinting, (9) agent mode capabilities present but auth-gated (`edit_mode_hidden` flag), (10) identity layer is bimodal — strongest when authenticated, weakest when not. 10 findings fed back. Proposed Class A bimodal weight calibration (Identity 0.15→0.25 when authenticated). Full results: `LAB-RUN-005-RESULTS.md` |
| LAB-RUN-007 | 2026-03-02 | OpenClaw v2026.3.1 | OC-POS-01: Standard install + onboard + agentic task + skill creation | **Conditional Pass** | **First Class D (Persistent Autonomous Agent) validated. New highest confidence score: 0.80 (High) — surpasses Cursor (0.79). First tool OUTSIDE original 10-tool scope.** 18/27 IOCs confirmed, 5 confirmed architecturally. Key findings: (1) `KeepAlive + RunAtLoad` LaunchAgent is strongest persistence of any tool, (2) LaunchAgent embeds external credentials (JIRA token) in world-readable plist, (3) self-modification confirmed — agent wrote own skill with zero approval gate, (4) 215 MB `~/.openclaw/` with config/credentials/skills/sessions/logs/memory — richest file footprint, (5) strongest identity footprint (multi-provider API keys + chat platform creds + external service tokens), (6) `openclaw status` is richest single-command diagnostic, (7) gateway WS on `:18789` is persistent PID-attributable signal, (8) CLI is thin client to daemon (like Ollama), (9) Class D taxonomy formalized — OpenClaw is reference implementation. Weights: File 0.30, Process 0.25, Behavior 0.15. Gaps: multi-channel messaging not tested, proactive/cron not exercised, browser automation not tested. Full results: `LAB-RUN-007-RESULTS.md` |
| LAB-RUN-013 | 2026-03-05 | OpenClaw v2026.3.1 | OC-POS-05: Same protocol as OC-POS-01 with local LLM (Qwen 3.5 0.8B via Ollama) | **Conditional Pass** | **First local-LLM variant lab run. Confirms infrastructure IOCs are model-independent.** Confidence: 0.725 (Medium) — down from 0.80 (High) in LAB-RUN-007, delta −0.075 driven entirely by behavior layer. Key findings: (1) 0.8B model failed ALL tool-use tasks (shell exec, file creation, skill authoring) — behavioral IOCs are model-capability-dependent, (2) model inference traffic is entirely local (`127.0.0.1:11434`) but gateway still makes outbound `:443` (telemetry/channel), (3) OpenClaw + Ollama co-residency creates symbiotic detection pattern (`:18789` ↔ `:11434`), (4) model swap is config-only with no approval gate — behavioral risk is latent, (5) OpenClaw's own security audit flags small models as CRITICAL, (6) process/file/identity/persistence IOCs identical to LAB-RUN-007, (7) policy decision unchanged: Approval Required (driven by infrastructure, not model). Gaps: same as LAB-RUN-007 (multi-channel, browser, proactive not tested). Full results: `LAB-RUN-013-RESULTS.md` |
| LAB-RUN-014 | 2026-03-05 | Claude Cowork v1.1.4498 (Claude Desktop) | CW-POS-01: Standard install + launch + session analysis + teardown | **Pass** | **First Claude Cowork validation. New highest confidence score: 0.905 (High) — surpasses OpenClaw (0.80). First tool with VM-based execution.** 12 processes (+ VM XPC), ~546 MB RSS. Key findings: (1) Full Linux VM via Apple Virtualization framework — 10 GB `rootfs.img` is largest artifact of any tool, (2) cleartext `accountName` + `emailAddress` in every session JSON — strongest identity signal, (3) `coworkScheduledTasksEnabled` + `schedule` skill = "soft proactive" execution (Class D-adjacent), (4) DXT extensions enable cross-app automation (Chrome, Apple Notes) on host outside VM sandbox, (5) plugin marketplace with 19+ enterprise plugins, (6) `skill-creator` enables self-modification, (7) ShipIt auto-updater runs as root, (8) VM egress allowlist (22 domains) is novel compliance signal, (9) persistent TLS PID-attributable (like Cursor), (10) feature flags in process args enable version fingerprinting. New Section 4.1b created. Full results: `LAB-RUN-014-RESULTS.md` |

---

## 13. Shelved Work Items

The following issues are deferred until the core detection, policy, and enforcement framework is operational. They are tracked here to prevent scope loss.

| Issue | Title | Dependency | Reactivation Trigger |
|---|---|---|---|
| INIT-28 | Test Matrix Definition | Core framework running | First lab sprint complete |
| INIT-29 | Automated Replay Scenarios | INIT-28 | Test matrix populated |
| INIT-30 | Metrics Pipeline | Audit pipeline live | Event flow validated |
| INIT-31 | Evasion Suite | INIT-28, INIT-29 | Baseline detections passing |
| INIT-32 | Benchmark Report Generator | INIT-30 | Metrics pipeline live |
| INIT-33 | One-Page Capability Brief | Detection profiles validated | Lab evidence available |
| INIT-34 | Honest Gaps Brief | Lab runs complete | Empirical gap data exists |
| INIT-35 | Technical Deep-Dive Appendix | Full framework documented | Buyer engagement imminent |
| INIT-36 | Competitive Positioning Sheet | INIT-33, INIT-34 | Capability + gaps articulated |
| INIT-37 | Demo Script / Evidence Pack | Lab evidence available | Sales enablement needed |
| INIT-40 | Attack-Style Tactics Mapping | Detection profiles validated | Threat modeling phase |
| INIT-41 | Privacy/Legal Telemetry Review | Audit schema finalized | Pre-deployment legal gate |
| INIT-42 | Detection Content Update Process | Core detections stable | Operational maturity phase |

---

## Appendix A — Cross-Layer Correlation Rules

*Source: INIT-43, generalized across all tools*

These rules define how multi-layer signals combine to produce attribution confidence.

### Rule C1 — High-Confidence Attribution (≥0.75)

**Requires all of:**
- Process entrypoint identification + parent-child lineage
- At least one fresh artifact signal (file or config evidence)
- Either network timing alignment OR strong behavioral sequence continuity

**Enables:** Approval Required / Block enforcement actions

### Rule C2 — Medium-Confidence Attribution (0.45–0.74)

**Requires:**
- Any two layers align
- But missing process certainty OR artifact recency

**Enables:** Warn + step-up controls; analyst review for high-sensitivity targets

### Rule C3 — Low-Confidence Attribution (<0.45)

**Conditions:**
- Single-layer evidence only
- Or conflicting multi-layer signals

**Enables:** Detect-only telemetry enrichment; no hard enforcement

### Rule C4 — Ambiguity Override

**Trigger:** Layers materially conflict (e.g., process says unknown wrapper while network says generic endpoint)

**Action:** Downgrade confidence regardless of individual layer scores; route to Warn/Approval paths only

### Rule C5 — Session-Artifact Correlation Boost (from LAB-RUN-001)

**Trigger:** A single session UUID or correlation key links artifacts across 3+ layers (e.g., file, identity, and behavior evidence share the same session identifier)

**Action:** Boost confidence by +0.05. This is empirically justified — Claude Code's session UUID (`~/.claude/debug/`, `projects/`, `todos/`, `file-history/`, `session-env/`) links all five layers under one identifier, making cross-layer alignment trivially verifiable.

### Rule C6 — Evasion Intent Detection (from LAB-RUN-EVASION-001)

**Trigger:** Any of the following detected alongside positive tool identification:
- Claude Code settings file contains `includeCoAuthoredBy: false` or `attribution.commit: ""`
- Local or global `commit-msg` hook contains patterns matching AI trailer stripping (`grep -v "Co-Authored-By"`)
- `git config init.templatedir` points to a directory containing trailer-stripping hooks

**Action:** Boost confidence by +0.15 and escalate to **Approval Required** enforcement. The presence of evasion tooling is itself an intent signal — it indicates the user is aware of detection and actively circumventing it. This is a stronger governance signal than the trailer itself.

**Note:** Absence of evasion indicators does NOT imply compliance. The `commit-msg` hook vector leaves no trace in git history.

### Confidence Penalty Reference

| Condition | Penalty |
|---|---|
| Missing parent-child process chain | −0.15 |
| Wrapper/renamed binary without lineage resolution | −0.15 |
| Stale artifact only (no recent modification) | −0.10 |
| Non-default artifact paths | −0.10 |
| Ambiguous proxy/gateway route | −0.10 |
| Unresolved process-to-network linkage | −0.10 |
| Containerized/remote execution reducing host telemetry | −0.10 |
| Weak/missing identity correlation | −0.10 |
| Polling-based network capture only (no EDR/ESF process-to-socket linkage) | −0.05 (new, from LAB-RUN-001) |
| Extension-host process indistinguishable from other extensions | −0.05 (new, from LAB-RUN-005) |

### Confidence Boost Reference (Evasion Indicators)

| Condition | Boost | Source |
|---|---|---|
| AI attribution suppression in tool settings | +0.15 | LAB-RUN-EVASION-001 |
| Trailer-stripping git hooks detected | +0.15 | LAB-RUN-EVASION-001 |
| Global template hooks for systematic stripping | +0.20 | LAB-RUN-EVASION-001 |
| Force-push after amend/rebase on monitored branch | +0.10 | LAB-RUN-EVASION-001 |

---

## Appendix B — Confidence Scoring Reference

### Layer Weight Defaults

| Layer | Default Weight | Rationale |
|---|---|---|
| Process / Execution | 0.30 | Strongest execution truth anchor |
| File / Artifact | 0.20 | Durable forensic evidence |
| Network | 0.15 | Corroborative, not primary |
| Identity / Access | 0.15 | Governance enforceability |
| Behavior | 0.20 | Agentic activity classification |

*Note: INIT-43 defines tool-specific weights (Process: 0.45, File: 0.30, Network: 0.25) for the three-layer signal map. The five-layer defaults above distribute across all layers and should be calibrated per-tool during lab runs.*

### Score Calculation (Simplified)

```
base_score = Σ (layer_weight × layer_signal_strength)
penalties  = Σ (applicable penalty conditions)
final_confidence = max(0, base_score - penalties)

Classification:
  final_confidence ≥ 0.75  → High
  0.45 ≤ final < 0.75     → Medium
  final < 0.45            → Low
```

### Calibration Requirements

- Layer weights and penalties are starting values
- Must be calibrated through lab replay runs (Section 12)
- Per-tool weight adjustments permitted when empirically justified
- All calibration changes must be versioned and traceable

### Empirical Calibration Data (from LAB-RUN-001)

**Claude Code v2.1.59 — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.85 | 0.255 | Clean attribution. Child processes transient — require <1s polling or ESF. |
| File | 0.20 | 0.95 | 0.190 | Strongest standalone signal. 308 files, unique structure. Consider weight increase to 0.25. |
| Network | 0.15 | 0.30 | 0.045 | Weakest signal without EDR. Polling at 2s intervals cannot attribute to PID. Consider weight decrease to 0.10 for polling-only. |
| Identity | 0.15 | 0.80 | 0.120 | OAuth profile richer than expected. Stronger than env-var-based detection. |
| Behavior | 0.20 | 0.75 | 0.150 | Agentic loop confirmed. Git IOC task-dependent. |

**Computed scores:**
- Five-layer default weights: **0.71 (Medium)**, penalty −0.05 for unresolved proc-net linkage
- Three-layer INIT-43 weights: **0.69 (Medium)**
- Projected with EDR-grade network: **~0.82 (High)**

**Recommended weight adjustment for Claude Code (pending second lab run validation):**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| File | 0.20 | 0.25 | Dominant signal — unique, large, high-confidence standalone |
| Network | 0.15 | 0.10 | Weak without EDR; short-lived HTTPS bursts evade polling |
| Process | 0.30 | 0.30 | No change — strong and reliable |
| Identity | 0.15 | 0.15 | No change — strong with OAuth, but may vary by auth method |
| Behavior | 0.20 | 0.20 | No change — solid but task-dependent variance |

### Empirical Calibration Data (from LAB-RUN-003)

**Ollama v0.17.0 — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.90 | 0.270 | Clean daemon identification. Client-server model (CLI ≠ child of daemon) — requires dual detection. |
| File | 0.20 | 0.90 | 0.180 | Large, unique model storage (652 MB, 13 files). OCI manifests, content-addressable blobs, ed25519 keypair. |
| Network | 0.15 | 0.70 | 0.105 | Persistent localhost listener trivially attributable. Outbound pull not captured via pcap (no sudo). |
| Identity | 0.15 | 0.50 | 0.075 | Weakest layer — no accounts, no OAuth, no API keys. OS user ownership only. Architectural ceiling. |
| Behavior | 0.20 | 0.80 | 0.160 | Inference burst cadence, scripted automation, model management all confirmed. |

**Computed scores:**
- Five-layer default weights: **0.69 (Medium)**, penalty −0.10 (−0.05 partial proc-net linkage, −0.05 weak identity)
- Projected with EDR + model policy: **~0.79 (High)**

**Recommended weight adjustment for Ollama / Class B tools:**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Daemon is easily detectable but less distinctive than CLI tools — many services listen on localhost |
| File | 0.20 | 0.25 | Model storage is large, unique, persistent. Content-addressable blobs are distinctive |
| Network | 0.15 | 0.20 | Persistent localhost listener inverts difficulty vs Class C HTTPS bursts |
| Identity | 0.15 | 0.10 | Architecturally weak — inherent ceiling for Class B local runtimes |
| Behavior | 0.20 | 0.20 | No change — inference cadence and model management are solid signals |

### Empirical Calibration Data (from LAB-RUN-004)

**Cursor v2.5.26 — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.95 | 0.285 | Exceptional. 29-process tree with labeled extension hosts. `agent-exec` is binary Class C indicator. Code-signed by Cursor Inc. |
| File | 0.20 | 0.90 | 0.180 | Agent transcripts, ai-tracking.db, plans, tools. 63 files, 14 MB. Smaller than Claude Code but high quality per file. |
| Network | 0.15 | 0.75 | 0.1125 | Persistent TLS to Cursor cloud, PID-attributable. Extension-host labels differentiate Class A vs C traffic. Without pcap, SNI unconfirmed. |
| Identity | 0.15 | 0.55 | 0.0825 | Weakest layer. Account state in Electron user-data-dir, not examined. OS user and code signing are available signals. |
| Behavior | 0.20 | 0.90 | 0.180 | Agent loop confirmed. `agent-exec` process is unique Class C indicator. `Made-with: Cursor` git trailer. |

**Computed scores:**
- Five-layer default weights: **0.79 (High)**, penalty −0.05 for weak identity correlation
- Projected with account state from user-data-dir: **~0.85 (High)**

**Recommended weight adjustment for Cursor / Class A→C tools:**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| Process | 0.30 | 0.30 | No change — process tree is the strongest signal with labeled extension hosts |
| File | 0.20 | 0.20 | No change — agent transcripts and ai-tracking.db are high-quality artifacts |
| Network | 0.15 | 0.20 | Persistent TLS easily attributed to PIDs; extension-host labels enable class differentiation |
| Identity | 0.15 | 0.10 | Account state in Electron user-data-dir not accessible in standard scan; OS user only |
| Behavior | 0.20 | 0.20 | No change — agentic loop confirmed with all IOCs |

### Empirical Calibration Data (from LAB-RUN-005)

**GitHub Copilot (github.copilot-chat v0.37.9 in VS Code 1.109.5) — five-layer observed signal strengths (unauthenticated scenario):**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.80 | 0.240 | Strong process identification. Electron → extension host tree is clear. But extension host is shared by ALL extensions — Copilot-specific attribution requires cross-layer correlation. |
| File | 0.20 | 0.85 | 0.170 | Extension directory (242 files) is unique. Telemetry logs contain machineId, devDeviceId, session UUID, experiment flags. Footprint between Claude Code (308 files) and Ollama (13 files). |
| Network | 0.15 | 0.55 | 0.083 | Persistent HTTPS connections from dedicated Network Service process — easily attributable. But without TLS/SNI, cannot confirm Copilot-specific endpoints vs general VS Code telemetry. No inference traffic (unauthenticated). |
| Identity | 0.15 | 0.40 | 0.060 | **Bimodal layer.** In this unauthenticated run: 0 GitHub sessions, no keychain entry. Device-level IDs (machineId, devDeviceId) present. Projected ~0.90 when authenticated with org-managed account. |
| Behavior | 0.20 | 0.25 | 0.050 | No active Copilot behavioral signals (unauthenticated). Passive signals only: experiment flag queries. Projected ~0.70 with active suggestions/chat. |

**Computed scores:**
- Five-layer default weights: **0.45 (Medium, barely)**, penalty −0.15 (−0.05 partial proc-net, −0.05 weak identity, −0.05 extension-host ambiguity)
- Projected with authentication + active usage: **~0.74 (Medium, upper)**
- Projected with EDR + org auth: **~0.80 (High)**

**Recommended weight adjustment for Copilot / Class A tools:**

| Layer | Current | Proposed (Unauth) | Proposed (Auth) | Justification |
|---|---|---|---|---|
| Process | 0.30 | 0.25 | 0.20 | Extension host shared by all extensions — less distinctive than standalone processes |
| File | 0.20 | 0.25 | 0.20 | Extension directory and telemetry logs are strong, unique. Device IDs provide persistent identity |
| Network | 0.15 | 0.15 | 0.15 | No change — persistent connections easy to detect, but endpoint attribution needs TLS/SNI |
| Identity | 0.15 | 0.15 | 0.25 | **Bimodal:** increase significantly for authenticated scenarios — GitHub account state is primary governance lever for Class A |
| Behavior | 0.20 | 0.20 | 0.20 | No change — should be strong when Copilot is active |

**New penalty (from LAB-RUN-005):**

| Condition | Penalty | Source |
|---|---|---|
| Extension-host process indistinguishable from other extensions | −0.05 | LAB-RUN-005 |

### Empirical Calibration Data (from LAB-RUN-006)

**Open Interpreter v0.4.3 — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.70 | 0.210 | Generic `python3` name reduces value. IPyKernel indirection. Module-path matching required. |
| File | 0.20 | 0.65 | 0.130 | Weakest file layer of any tested tool. Zero persistent state outside venv. Venv location arbitrary. |
| Network | 0.15 | 0.55 | 0.083 | Provider-dependent target. Localhost (Ollama) easily captured; cloud API has same polling issues as Claude Code. |
| Identity | 0.15 | 0.55 | 0.083 | OS user only. API key in env vars, not persisted. No account profiles. |
| Behavior | 0.20 | 0.85 | 0.170 | **Strongest signal.** Command-chain (pip install → pytest) is primary detection anchor. auto_run is key risk marker. |

**Computed scores:**
- Five-layer default weights: **0.525 (Medium)**, penalty −0.15 (−0.05 non-default paths, −0.05 proc-net linkage, −0.05 weak identity)
- Projected with EDR: **~0.68 (Medium)**

**Recommended weight adjustment for Open Interpreter / Python-based Class C tools:**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Generic process name reduces value. Module-path matching required |
| File | 0.20 | 0.15 | Ephemeral session model — zero state outside venv. Weakest file layer tested |
| Network | 0.15 | 0.15 | No change — provider-dependent target |
| Identity | 0.15 | 0.10 | Env-var credentials only, no persistent identity store |
| Behavior | 0.20 | 0.35 | Dominant signal — command-chain pattern is the primary detection anchor |

### Empirical Calibration Data (from LAB-RUN-007)

**OpenClaw v2026.3.1 — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.30 | 0.90 | 0.270 | Named `openclaw-gateway` process with LaunchAgent persistence. Clear daemon + CLI client-server model (like Ollama). `KeepAlive + RunAtLoad` is strongest persistence mechanism tested. |
| File | 0.20 | 0.95 | 0.190 | Richest file footprint of any tested tool. 215 MB `~/.openclaw/` with config, credentials, skills, sessions, logs, memory, workspace, and device state. Self-authored skill confirmed. |
| Network | 0.15 | 0.70 | 0.105 | Gateway WS listener on `:18789` trivially attributable via `lsof` (like Ollama). Model provider traffic confirmed indirectly. Chat platform connections confirmed at config level. |
| Identity | 0.15 | 0.85 | 0.1275 | Strongest identity footprint of any tested tool. Multi-provider API keys, chat platform credentials, external service tokens (JIRA), gateway token. All centralized in config and LaunchAgent plist. |
| Behavior | 0.20 | 0.80 | 0.160 | Shell execution and self-modification confirmed. Multi-file burst-write observed. Proactive/scheduled and multi-channel capabilities confirmed architecturally but not exercised. |

**Computed scores:**
- Five-layer default weights: **0.80 (High)**, penalty −0.05 (partial proc-net linkage)
- Projected with EDR + active channel monitoring: **~0.90 (High)**

**Recommended weight adjustment for OpenClaw / Persistent Autonomous Agents:**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Named daemon is distinctive but less critical than file layer for forensic value. LaunchAgent is the key persistence signal. |
| File | 0.20 | 0.30 | Dominant signal — 215 MB directory with config, credentials, skills, sessions, logs, memory. Richest footprint tested. |
| Network | 0.15 | 0.15 | No change — gateway listener is strong, but model API traffic has same polling challenges as other tools. |
| Identity | 0.15 | 0.15 | No change — strongest identity layer tested, but high signal strength compensates without weight increase. |
| Behavior | 0.20 | 0.15 | Less dominant than file layer. Self-modification and shell execution confirmed, but artifacts produced are the primary detection anchors. |

### Empirical Calibration Data (from LAB-RUN-013)

**OpenClaw v2026.3.1 with local LLM (Qwen 3.5 0.8B via Ollama) — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note | LAB-RUN-007 Δ |
|---|---|---|---|---|---|
| Process | 0.30 | 0.85 | 0.255 | Same named daemon + LaunchAgent persistence. Slightly lower than LAB-RUN-007 (0.90) because no child process chains observed (model too small for tool use). | −0.05 |
| File | 0.20 | 0.95 | 0.190 | **Identical to LAB-RUN-007.** 216 MB `~/.openclaw/` with same structure. Config now points to `ollama/qwen3.5:0.8b`. Model-independent. | 0.00 |
| Network | 0.15 | 0.65 | 0.0975 | Gateway `:18789` confirmed. Inference traffic is local (`:11434`). Gateway still makes one outbound `:443` connection. Lower than LAB-RUN-007 (0.70) because no outbound model API calls. | −0.05 |
| Identity | 0.15 | 0.80 | 0.120 | Plist credentials, env API keys present. Active model uses placeholder key (`ollama-local`). Slightly lower (0.85 → 0.80) because active auth is a placeholder. | −0.05 |
| Behavior | 0.20 | 0.40 | 0.080 | **KEY DIFFERENCE.** 0.8B model failed all tool-use tasks: shell execution, file creation, skill authoring. Simple Q&A succeeded. Behavioral risk is *latent*, not absent — a config-only model swap restores full capability. | −0.40 |

**Computed scores:**
- Five-layer default weights: **0.74 (Medium)**, penalty −0.05 (partial proc-net linkage) → **0.6925**
- OpenClaw calibrated weights: **0.775 (Medium/High)**, penalty −0.05 → **0.725 (Medium)**
- LAB-RUN-007 comparison: **0.80 (High)** — delta: **−0.075**, driven entirely by behavior layer

**Key insight:** Infrastructure-based detection (process, file, persistence, network listeners) is **model-independent**. Behavioral detection is **model-capability-dependent**. A confidence floor for Class D tools with strong infrastructure signals would prevent underscoring when the model is temporarily incapable.

### Empirical Calibration Data (from LAB-RUN-014)

**Claude Cowork v1.1.4498 (Claude Desktop) — five-layer observed signal strengths:**

| Layer | Default Weight | Observed Signal | Weighted | Calibration Note |
|---|---|---|---|---|
| Process | 0.25 | 0.90 | 0.225 | Multi-process Electron (12 processes) + Apple Virtualization.VirtualMachine XPC service. VM process is unique IOC — no other tool has this. ShipIt auto-updater runs as root. |
| File | 0.15 | 0.95 | 0.1425 | **Largest footprint of any tool: 10 GB.** VM bundle (9.6 GB rootfs.img), session JSONs with audit.jsonl, DXT extensions, skills plugin, marketplace clone. Pathognomonic `vm_bundles/claudevm.bundle/`. |
| Network | 0.15 | 0.80 | 0.120 | 15 persistent TLS connections from Network utility. PID-attributable at any polling interval (like Cursor). VM egress allowlist (22 domains) is novel compliance signal. VM has dedicated IP/MAC. |
| Identity | 0.10 | 0.90 | 0.090 | **Strongest identity signal of any tool.** Cleartext `accountName` + `emailAddress` in every session JSON. Code signing: Anthropic PBC. VM machineIdentifier persists across sessions. |
| Behavior | 0.15 | 0.85 | 0.1275 | Multi-step agentic execution confirmed via audit.jsonl (56 events). Shell execution in VM. MCP connector CRUD. Scheduled tasks and self-modification architecturally confirmed. |
| Binary Hash | 0.20 | 1.00 | 0.200 | Signed app at known path with Anthropic code signing. Highest-confidence binary attribution. |

**Computed scores:**
- Six-layer default weights (incl. binary hash): **0.905 (High)**, zero penalties — new highest
- Proposed calibrated weights (File 0.20, Identity 0.15, Network 0.10, Behavior 0.10): **0.915 (High)**

**Recommended weight adjustment for Claude Cowork:**

| Layer | Current | Proposed | Justification |
|---|---|---|---|
| Process | 0.25 | 0.25 | No change — VM XPC service is unique. Multi-process Electron is distinctive. |
| File | 0.15 | 0.20 | 10 GB footprint is unmistakable. VM bundle is pathognomonic. |
| Network | 0.15 | 0.10 | Persistent but centralized in one Network utility process. |
| Identity | 0.10 | 0.15 | Cleartext email is strongest identity signal of any tool. |
| Behavior | 0.15 | 0.10 | Audit trail strong but app-dependent. Scheduled tasks not exercised. |
| Binary Hash | 0.20 | 0.20 | Signed binary is definitive anchor. |

### Cross-Tool Calibration Comparison

| Layer | Claude Code (C) | Ollama (B) | Cursor (A→C) | Copilot (A) | Open Interpreter (C) | OpenClaw cloud (D) | OpenClaw local (D) | Claude Cowork (C+) | Interpretation |
|---|---|---|---|---|---|---|---|---|---|
| Process | 0.85 | 0.90 | **0.95** | 0.80 | 0.70 | 0.90 | 0.85 | 0.90 | Cowork VM XPC service is unique. |
| File | **0.95** | 0.90 | 0.90 | 0.85 | 0.65 | **0.95** | **0.95** | **0.95** | Cowork's 10 GB = 50× OpenClaw. |
| Network | 0.30 | 0.70 | **0.75** | 0.55 | 0.55 | 0.70 | 0.65 | **0.80** | Persistent TLS + VM egress allowlist. |
| Identity | **0.80** | 0.50 | 0.55 | 0.40* | 0.55 | **0.85** | 0.80 | **0.90** | **Strongest.** Cleartext email. |
| Behavior | 0.75 | 0.80 | 0.90 | 0.25* | **0.85** | 0.80 | **0.40** | 0.85 | Audit trail + MCP connectors. |
| **Final** | **0.71** | **0.69** | **0.79** | **0.45** | **0.525** | **0.80** | **0.725** | **0.905** | **New highest.** VM + identity. |

**Key insights:**

1. **Claude Cowork achieves the highest confidence score (0.905) of any tested tool**, surpassing OpenClaw (0.80). This is driven by the richest file and identity footprints in the playbook. The combination of persistent daemon, rich config directory, embedded credentials, and self-modification creates an exceptionally detectable tool — which is also the highest-risk.

2. **Cursor's multi-process Electron architecture is a governance advantage.** Labeled extension-host types provide process-level class indicators unique to IDE-class tools. Combined with persistent network connections (unlike CLI tools) and complete agent transcripts (unlike daemon tools), Cursor achieves the second-highest confidence.

3. **Class A tools have a bimodal detection profile driven by authentication state.** Copilot scores Medium-barely when unauthenticated but would score near-High when authenticated with an org-managed GitHub account. Weight calibration for Class A tools must account for this bimodality — identity weight should be context-dependent.

4. **Each tool class has a different weakest layer:** Class A (Copilot) = Process (shared extension host), Class B (Ollama) = Identity (no account system), Class C varies: Claude Code = Network (ephemeral HTTPS), Open Interpreter = File (ephemeral state) + Process (generic name), OpenClaw = Network (model API traffic, same as others). Per-tool weight calibration is now empirically justified.

5. **Milestone: empirical data now exists for all three tool classes (A, B, C) with three Class C data points plus one beyond the original 10-tool scope.** With LAB-RUN-007, we have a tool that straddles class boundaries. The default five-layer weights can now be calibrated per-tool with empirical justification.

6. **Class C detection profiles are NOT generalizable — confirmed with a third data point.** Claude Code (0.71), Open Interpreter (0.525), and OpenClaw (0.80) are all Class C but have dramatically different detection profiles. OpenClaw is file+identity-anchored; Claude Code is file-anchored; Open Interpreter is behavior-anchored. Weight calibration must be per-tool within Class C.

7. **Class D is now formalized with OpenClaw as the reference implementation.** OpenClaw's combination of Class C execution + Class B daemon persistence + novel capabilities (self-modification, multi-channel communication, proactive execution) satisfies all four Class D criteria. Future tools with persistent autonomous agent profiles (e.g., OpenAI agent platform, Anthropic agent infrastructure) should be evaluated against the Class D criteria in Section 5.1.

8. **Behavioral detection is model-capability-dependent (LAB-RUN-013).** A 0.8B model on the same OpenClaw infrastructure could not perform any tool-use tasks (shell execution, file creation, self-modification), dropping the behavior signal from 0.80 to 0.40. Infrastructure-based IOCs (process, file, identity, persistence) were unchanged. Detection strategies must not rely solely on observed behavior — a tool with incapable model is still a tool with capable infrastructure.

9. **Local LLM eliminates cloud model API traffic but creates co-residency detection patterns.** OpenClaw + Ollama running together (`:18789` ↔ `:11434`) is a new cross-tool IOC not seen with any other tool pair. Gateway-to-Ollama loopback connections provide positive evidence of a local autonomous agent configuration.

10. **Model swap is a config-only change with zero audit trail.** Switching from a small, incapable local model to a large, fully agentic cloud model requires editing one JSON field in `openclaw.json`. There is no approval gate or audit mechanism. Behavioral risk is *latent* in infrastructure-class tools — a point-in-time confidence score may underrepresent true risk.

---

*End of Playbook v0.3.1 — Updated 2026-03-05 with LAB-RUN-014 findings (Claude Cowork: VM-based execution, 10 GB footprint, cleartext identity, "soft proactive" scheduled tasks, DXT cross-app automation, 0.905 confidence — new highest)*

**Next actions:**
1. ~~Execute first lab sprint (Section 12.3 priority order)~~ — **In progress.** Claude Code CC-POS-01 + CC-POS-02 complete. Ollama OL-POS-01 complete. Cursor CUR-POS-01 complete. Copilot CP-POS-01 complete. **Open Interpreter OI-POS-01 complete.**
2. ~~Co-Authored-By evasion test~~ — **Complete.** 6/6 evasion vectors succeeded. Trailer reclassified as one-way signal. Evasion counter-indicators added to Section 4.1, Rule C6 added to Appendix A.
3. ~~Ollama lab run (LAB-RUN-003)~~ — **Complete.** Class B framework generalization validated. 9/9 IOCs confirmed. Proposed per-class weight calibration. Section 4.4 updated with lab findings.
4. ~~Cursor lab run (LAB-RUN-004)~~ — **Complete.** First Class A→C tool validated. First High confidence score (0.79). `agent-exec` extension host confirmed as binary Class C indicator. 9/9 IOCs confirmed + 10 new findings. Section 4.2 updated with lab findings.
5. ~~Copilot lab run (LAB-RUN-005)~~ — **Complete (unauthenticated baseline).** First pure Class A tool validated. Milestone: empirical data for all three tool classes (A, B, C). 4/11 IOCs confirmed, 2 partial, 5 not observed. Bimodal identity profile documented.
6. ~~Open Interpreter lab run (LAB-RUN-006)~~ — **Complete.** Second Class C tool validated. **Key finding: Class C profiles are NOT generalizable.** OI scored 0.525 vs Claude Code's 0.71 — inverted detection anchors (behavior vs file). 10/14 IOCs confirmed. Ephemeral session model, generic process name, and Jupyter/IPyKernel code execution architecture documented. Section 4.7 updated with lab findings.
7. ~~OpenClaw lab run (LAB-RUN-007)~~ — **Complete.** First persistent autonomous agent validated. **New highest confidence: 0.80 (High).** First tool outside original 10-tool scope. 18/27 IOCs confirmed. Self-modification, LaunchAgent persistence, credential exposure in plist, 215 MB forensic footprint. Section 4.11 created and updated with lab findings. Three-class taxonomy discussion initiated.
8. **CP-POS-02:** Repeat Copilot lab with authenticated GitHub org-managed account. **Highest priority** — closes the largest gap from CP-POS-01.
9. **OI-POS-02:** Open Interpreter multi-step automation with restricted paths. Validates credential-store and restricted-path IOCs not triggered in OI-POS-01.
10. **OI-EVA-01:** Wrapped launch, ephemeral venv/container. Validates the primary OI evasion scenario (Section 12.1). Test: rename venv, invoke via `python -m interpreter`, delete venv post-session.
11. **CP-EVA-01:** Personal account on managed endpoint, proxy route.
12. **CP-POS-03:** Exercise Copilot agent/edit mode.
13. **CUR-POS-02:** Multi-file refactor + git workflow in agentic mode.
14. **CUR-EVA-01:** Wrapped launch path / proxy attribution evasion.
15. **CUR-EVA-02:** `Made-with: Cursor` git trailer suppression.
16. **CUR-IDENTITY-01:** Deep examination of `~/Library/Application Support/Cursor/` for account/auth state.
17. **OL-POS-02:** Ollama local API automation session.
18. **OL-EVA-01:** Custom port + containerized evasion.
19. **CC-POS-03:** Shell tool usage scenario in a sensitive repo context.
20. **OC-POS-02:** OpenClaw multi-channel messaging integration (WhatsApp/Telegram). Validates chat platform connection IOCs and external-input-to-local-execution pipeline. Requires test messaging accounts.
21. **OC-POS-03:** OpenClaw cron/proactive execution. Configure a heartbeat or cron job and capture autonomous agent turn triggered by schedule. Validates the novel "proactive execution without user prompt" IOC.
22. **OC-POS-04:** OpenClaw browser automation. Exercise the browser tool to validate CDP-controlled Chrome/Chromium child processes and browser automation traffic IOCs.
23. **OC-EVA-01:** Renamed binary, custom port (`--port`), containerized gateway (Docker). Validates primary OpenClaw evasion scenarios.
24. **~~Class D taxonomy discussion:~~** ~~Prepare a Class D definition~~ → **Complete.** Class D ("Persistent Autonomous Agents") is now formalized in Section 5.1. OpenClaw is the reference implementation. Monitor emerging tools against the four Class D criteria: OpenAI agent platform, Anthropic agent infrastructure, similar open-source persistent agents.
25. **LaunchAgent credential exposure audit:** OpenClaw's plist embeds external service credentials (JIRA, gateway tokens) in world-readable mode. Audit all LaunchAgent plists across tested tools for credential exposure. Consider adding a plist credential scan to the standard lab protocol.
26. **JSON Schema formalization** from event model — empirical data now available from **9 lab runs** across all 3 classes + persistent agent (cloud + local LLM variants).
27. **Per-tool weight calibration formalization** — empirical data from 6 tools now supports per-tool weight profiles. **OpenClaw + Open Interpreter data proves per-tool (not per-class) calibration is needed.** LAB-RUN-013 adds model-dependent behavioral weight dimension.
28. **OC-POS-05 (LAB-RUN-013):** ~~OpenClaw with local LLM (Qwen 3.5 0.8B via Ollama).~~ — **Complete.** Confirms infrastructure IOCs are model-independent. Behavioral IOCs model-capability-dependent. Confidence: 0.725 (Medium). Policy: Approval Required (same as cloud variant). See `LAB-RUN-013-RESULTS.md`.
29. ~~Synthetic fixture tests for 5 new scanners~~ → **Complete.** 22 tests across Aider, LM Studio, Continue, GPT-Pilot, and Cline validate scanner detection logic without tool installs. See Section 11.6 for architecture, Section 12.4 for methodology findings. Scanner parsing, class escalation, risk assignment, and unapproved-backend detection all confirmed. Live lab runs still needed for runtime behavior validation.
30. **Confidence floor for infrastructure-class tools** — LAB-RUN-013 suggests a floor based on process + file signal strength (both ≥ 0.80) to prevent underscoring tools with capable infrastructure but temporarily incapable models. Design and implement.
31. Reactivate shelved items per dependency triggers (Section 13)
32. Iterate this document based on lab findings
33. **~~CW-POS-01 (LAB-RUN-014):~~** ~~Claude Cowork standard install + launch + session analysis + teardown.~~ — **Complete.** First Cowork validation. **New highest confidence: 0.905 (High).** VM-based execution model is unique. 10 GB footprint is largest. Cleartext email is strongest identity. Scheduled tasks = "soft proactive." Section 4.1b created. See `LAB-RUN-014-RESULTS.md`.
34. **CW-POS-02:** Exercise Claude Cowork scheduled task creation and execution. Validate the `schedule` skill runtime behavior with a recurring cron task. Confirm whether scheduled tasks actually execute while app is idle.
35. **CW-POS-03:** Exercise DXT browser automation (`chrome-control`). Validate Chrome tab management, JavaScript execution, and page content retrieval via AppleScript. Capture host-side process spawning for AppleScript.
36. **CW-EVA-01:** Non-standard install path, VPN-routed API traffic. Test detection when Claude Desktop is installed outside `/Applications/`.
37. **"Soft proactive" classification formalization:** Define the intermediate state between Class C (user-triggered) and Class D (always-on) for tools with scheduled task capability but no daemon persistence. Claude Cowork is the reference implementation for this category.
