# Agentic AI Endpoint Detection & Governance Playbook

**Version:** 0.1 — Initial Framework  
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
| Detection profiles: 10 tools (INIT-13–22) | Test matrix definition (INIT-28) |
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

### 4.2 Cursor (INIT-14)

**Class:** A (SaaS Copilot / Assistive IDE); escalates to C when terminal agent workflows execute  
**Risk Posture:** Medium baseline, High in agentic mode

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | Signed Cursor app process from standard install paths (`/Applications/Cursor.app`, `%LocalAppData%\Programs\Cursor`) | High |
| **Process** | Child process lineage: Cursor → embedded terminal → shell/git/node | High |
| **Process** | Sustained session with child process and file-write bursts | Medium |
| **File** | `~/.cursor/`, workspace `.cursor/` settings and extension state files | Medium |
| **File** | AI feature cache/session files with recent timestamps | Medium |
| **File** | Burst edits across repo files with consistent timing | Medium |
| **Network** | TLS/SNI to Cursor cloud/model infrastructure endpoints | Medium |
| **Network** | Request bursts aligned with prompt-response editing cycles | Medium |
| **Identity** | Cursor account state (corporate vs personal) on managed endpoint | Medium |
| **Behavior** | High-frequency multi-file edit loops after prompt interaction cadence | High |
| **Behavior** | Context-heavy reads + concentrated writes (agentic edit shape) | High |
| **Behavior** | Shell invocations proximate to AI edit sequences | High |

#### Evasion Vectors
- Portable/non-standard installs and launch wrappers
- Containerized/remote dev sessions
- Shared model endpoints masking attribution
- Forked/customized builds altering expected artifacts

---

### 4.3 GitHub Copilot (INIT-15)

**Class:** A (SaaS Copilot / Assistive IDE Feature)  
**Risk Posture:** Medium

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | IDE host process (VS Code/JetBrains) + Copilot extension host subprocess | Medium–High |
| **Process** | Extension-host activity tied to chat/agent-style workflows | Medium |
| **File** | Copilot extension install manifests (`extensions/GitHub.copilot*`) | Medium |
| **File** | Workspace extension settings, policy files, local logs/caches | Medium |
| **Network** | Traffic to `copilot-proxy.githubusercontent.com`, GitHub Copilot API endpoints | Medium |
| **Network** | Burst timing aligned with suggestion/chat activity | Low–Medium |
| **Identity** | GitHub account auth state (org-managed vs personal) | High |
| **Identity** | License/entitlement context from org policy | High |
| **Behavior** | Suggestion acceptance cadence + rapid edit bursts | Medium |
| **Behavior** | AI-chat-to-edit sequences across multiple files | Medium–High |
| **Behavior** | High-volume generated changes without normal review cadence | High (risk marker) |

#### Evasion Vectors
- Personal GitHub accounts on managed endpoints
- Remote dev containers with partial host telemetry
- Extension forks/alternate clients
- Shared endpoints with weak identity correlation

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

#### Concrete IOCs

| Layer | Indicator | Confidence Weight |
|---|---|---|
| **Process** | Python runtime mapped to Open Interpreter entrypoints/modules | High |
| **Process** | Parent lineage: terminal/script → open-interpreter → child command chains | High |
| **Process** | Privilege context: effective uid/admin elevation during sessions | High (risk marker) |
| **File** | `open-interpreter` package in venv/site-packages | High |
| **File** | Session history/transcript artifacts | Medium |
| **File** | Short-window file write bursts aligned with command execution | Medium |
| **Network** | Model-provider API calls with burst timing matching action loops | Medium |
| **Network** | Outbound requests triggered as part of command workflows | Medium |
| **Identity** | Endpoint user identity mapped to interpreter runtime session | Medium |
| **Identity** | Credential/token exposure in runtime environment | High (risk marker) |
| **Behavior** | Plan→execute→revise loops with command bursts | High |
| **Behavior** | Repeated shell/file operations with low inter-command delay | High |
| **Behavior** | Package install + execution chain in same loop | High (risk marker) |
| **Behavior** | Credential-store touches / broad file fan-out in restricted paths | High (risk marker) |

#### Evasion Vectors
- Wrapper scripts masking invocation semantics
- Renamed/forked package distributions
- Containerized/remote execution
- Ephemeral virtualenv reducing artifact persistence

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

### IOC Summary: Quick-Reference Matrix

| Tool | Primary Process Signal | Key File Artifact | Key Network Indicator | Risk Class |
|---|---|---|---|---|
| Claude Code | `claude` CLI binary + child chains | `~/.claude/` config/state dirs | `api.anthropic.com` | C |
| Cursor | Signed `Cursor` app + embedded terminal children | `~/.cursor/` settings/extensions | Cursor cloud endpoints | A→C |
| Copilot | IDE + Copilot extension host subprocess | Extension manifests `GitHub.copilot*` | `copilot-proxy.githubusercontent.com` | A |
| Ollama | `ollama serve` daemon + CLI clients (HTTP, not child procs) | `~/.ollama/models/` (OCI blobs) + ed25519 keypair | Localhost `:11434` (unauth), `registry.ollama.ai` | B |
| LM Studio | LM Studio desktop process | Local model storage (GGUF files) | Loopback API, HuggingFace pulls | B |
| Continue | IDE + Continue extension host | `config.json` with backend targets | Varies per config | A→C |
| Open Interp. | Python + `open-interpreter` module | venv/site-packages, session artifacts | Model provider APIs | C |
| Aider | `aider` CLI + git subprocesses | `.aider*` config, concentrated edits | Model endpoint traffic | C |
| GPT-Pilot | Long-lived orchestrator process | Project tree generation artifacts | API bursts + dependency pulls | C |
| Cline | IDE + Cline extension host | Extension manifests + tool-call config | Backend model + tool-call traffic | A→C |

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

Each rule has a stable `rule_id`, version, and explainability payload.

### 6.4 Session-Level Escalation

The ladder is stateful within session context:
- First medium-risk event → Warn
- Repeated medium-risk events → Approval Required
- Repeated denied attempts → Block + incident flag

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

---

## 12. Lab Validation Runs

This section provides the framework for empirical validation. Each tool profile defines minimum positive and adversarial scenarios; this section tracks execution status and findings.

### 12.1 Validation Matrix (Minimum Per Tool)

| Tool | Positive Scenarios (≥3) | Evasion Scenarios (≥2) | Status |
|---|---|---|---|
| Claude Code | Standard CLI, multi-file refactor + git, shell tool usage | Renamed binary, proxy-routed API | `IN PROGRESS` (2/3 positive, 1/2 evasion) |
| Cursor | Standard editing, AI-assisted refactor, terminal workflow | Wrapped launch path, proxy attribution | `NOT STARTED` |
| Copilot | Org account normal use, chat-assisted edit, full-layer session | Personal account on managed endpoint, proxy route | `NOT STARTED` |
| Ollama | Approved model pull+run, inference session, local API automation | Custom port/container, side-loaded models | `IN PROGRESS` (1/3 positive) |
| LM Studio | Approved model load, model switch + prompts, identity-mapped use | Non-default path + renamed artifacts, non-default port | `NOT STARTED` |
| Continue | Approved backend workflow, config-defined backend switch, multi-file edit | Forked config to unsanctioned endpoint, proxy gateway | `NOT STARTED` |
| Open Interpreter | Benign command session, multi-step automation, policy-compliant repo task | Wrapped launch, ephemeral venv/container | `NOT STARTED` |
| Aider | Single-module change + PR, multi-file refactor, formatting/test session | Alias/wrapper invocation, devcontainer execution | `NOT STARTED` |
| GPT-Pilot | Greenfield scaffold, iterative gen+test loop, controlled module expansion | Forked launcher, containerized execution | `NOT STARTED` |
| Cline | Approved backend + code-assist, multi-file edit, controlled tool-calling | Forked extension build, shared proxy route | `NOT STARTED` |

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

### 12.5 Lab Run Log

| Run ID | Date | Tool | Scenario | Result | Notes |
|---|---|---|---|---|---|
| LAB-RUN-001 | 2026-02-26 | Claude Code v2.1.59 | CC-POS-01: Standard CLI install + agentic task | **Conditional Pass** | Confidence: 0.71 (Medium). 9/12 IOCs confirmed. Network layer under-instrumented. 10 findings fed back to playbook. Full results: `LAB-RUN-001-RESULTS.md` |
| LAB-RUN-002 | 2026-02-26 | Claude Code v2.1.59 | CC-POS-02: Multi-module project + git + tests | **Pass** | All three RUN-001 gaps closed: (1) terminal session recorded via `script` (5,629 lines), (2) git IOC confirmed — `git init` + `git add` + `git commit` with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer, (3) child process chain captured at 500ms polling: `claude` → `/bin/zsh` → `bash` → python/git. 6 source files, 199 LOC, 16 tests. Full results: `LAB-RUN-002-RESULTS.md` |
| LAB-RUN-EVASION-001 | 2026-02-26 | Claude Code v2.1.59 | CC-EVA-01: Co-Authored-By trailer evasion | **Pass (6/6 vectors succeeded)** | Tested 6 evasion vectors against the `Co-Authored-By` git trailer: settings suppression, amend, rebase, commit-msg hook, filter-branch, global template hook. **All succeeded.** Key finding: trailer is a high-confidence *positive* signal but a zero-confidence *negative* signal. Most dangerous vector: `commit-msg` hook strips trailer before it enters the object store — zero forensic trace. Added evasion counter-indicators to Section 4.1. Full results: `LAB-RUN-EVASION-001-RESULTS.md` |
| LAB-RUN-003 | 2026-02-26 | Ollama v0.17.0 | OL-POS-01: Standard install + model pull + inference | **Conditional Pass** | First Class B tool validated. Confidence: 0.69 (Medium). 9/9 Section 4.4 IOCs confirmed. Key findings: (1) Ed25519 keypair on first `serve` is new file IOC, (2) localhost:11434 listener trivially attributable — inverts network difficulty vs Class C, (3) unauthenticated API is governance risk, (4) identity layer architecturally weak (no accounts/OAuth), (5) OCI-format model manifests enable provenance tracing, (6) client-server process model (CLI ≠ child of daemon). 10 findings fed back. Proposed Class B weight calibration (Identity 0.15→0.10, File 0.20→0.25, Network 0.15→0.20). Full results: `LAB-RUN-003-RESULTS.md` |

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

### Cross-Tool Calibration Comparison

| Layer | Claude Code (Class C) | Ollama (Class B) | Delta | Interpretation |
|---|---|---|---|---|
| Process | 0.85 | 0.90 | +0.05 | Ollama's persistent daemon is slightly easier to detect than Claude Code's CLI |
| File | 0.95 | 0.90 | −0.05 | Claude Code's 308-file footprint is richer than Ollama's 13-file model storage |
| Network | 0.30 | 0.70 | +0.40 | **Largest gap.** Ollama's persistent listener vs Claude Code's ephemeral HTTPS |
| Identity | 0.80 | 0.50 | −0.30 | **Second largest gap.** Claude Code has OAuth; Ollama has OS user only |
| Behavior | 0.75 | 0.80 | +0.05 | Comparable — both show clear usage patterns when active |
| **Final** | **0.71** | **0.69** | −0.02 | Similar scores despite very different signal profiles |

**Key insight:** Class B and Class C tools score similarly overall but for completely different reasons. Class C tools are weak on network (short-lived HTTPS); Class B tools are weak on identity (no account system). Weight calibration should be per-class, not universal.

---

*End of Playbook v0.1 — Updated 2026-02-26 with LAB-RUN-003 findings*

**Next actions:**
1. ~~Execute first lab sprint (Section 12.3 priority order)~~ — **In progress.** Claude Code CC-POS-01 + CC-POS-02 complete. Ollama OL-POS-01 complete.
2. ~~Co-Authored-By evasion test~~ — **Complete.** 6/6 evasion vectors succeeded. Trailer reclassified as one-way signal. Evasion counter-indicators added to Section 4.1, Rule C6 added to Appendix A.
3. ~~Ollama lab run (LAB-RUN-003)~~ — **Complete.** Class B framework generalization validated. 9/9 IOCs confirmed. Proposed per-class weight calibration. Section 4.4 updated with lab findings.
4. **OL-POS-02:** Ollama local API automation session — validates scripted inference detection at scale.
5. **OL-EVA-01:** Custom port + containerized evasion — validates Class B evasion detection.
6. **CC-POS-03:** Shell tool usage scenario in a sensitive repo context. Validates R3/R4 action controls.
7. **JSON Schema formalization** from event model — empirical data now available from 4 lab runs.
8. Proceed to Open Interpreter (priority #2 in Section 12.3)
9. **Per-class weight calibration formalization** — empirical data from both Class B and Class C now supports distinct weight profiles.
10. Reactivate shelved items per dependency triggers (Section 13)
11. Iterate this document based on lab findings
