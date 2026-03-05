# LAB-RUN-014 Results: Claude Cowork Installation & Runtime Telemetry

**Run ID:** LAB-RUN-014  
**Date:** 2026-03-05  
**Tool:** Claude Cowork (Claude Desktop v1.1.4498, bundle ID `com.anthropic.claudefordesktop`)  
**Scenario ID:** CW-POS-01 (Standard install + launch + session analysis + teardown)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/cowork-lab/LAB-RUN-014/` (113 files, SHA-256 hashed per phase)  
**Comparison Runs:** LAB-RUN-004 (Cursor, Class A→C), LAB-RUN-001 (Claude Code, Class C)

> **Purpose:** First empirical validation of Claude Cowork. Determine detection profile, classification (A vs C vs D), and confidence score. Key hypothesis: Cowork shares Claude Code's API backend but has a radically different endpoint footprint due to VM-based execution.

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC | Status | Evidence | Notes |
|---|---|---|---|
| Signed Claude Desktop app process from `/Applications/Claude.app` | **Observed** | `phase2-onboard/all-claude-processes.txt`, `phase1-install/code-signing.txt` | Code-signed by `Developer ID Application: Anthropic PBC (Q6L2SF6YDW)`, notarized. Bundle ID: `com.anthropic.claudefordesktop`. Mach-O universal (x86_64 + ARM64). |
| Multi-process Electron architecture | **Observed** | `phase2-onboard/all-claude-processes.txt` | 12 processes: main, GPU helper, Network utility, 2× Plugin helpers (node.mojom.NodeService for DXT extensions), 3× Renderers, Crashpad handler, VirtualMachine XPC service, ShipIt auto-updater (runs as root). ~546 MB aggregate RSS. |
| Apple Virtualization framework VM process | **Observed** | `phase2-onboard/all-claude-processes.txt`, `phase1-install/vm-bundles.txt` | `com.apple.Virtualization.VirtualMachine` XPC service (PID 38548, 51 MB RSS). Full Linux VM with 10 GB `rootfs.img`, EFI boot, dedicated MAC (`fa:2d:c5:58:59:86`) and IP (`192.168.64.11`). **Novel IOC — no other profiled tool runs a VM.** |
| Plugin helper processes (DXT/MCP extension hosts) | **Observed** | `phase2-onboard/all-claude-processes.txt` | Two `Claude Helper (Plugin)` processes with `node.mojom.NodeService` — hosting `chrome-control` and `notes` DXT extensions. Analogous to Cursor's labeled extension-host types but with MCP protocol. |
| ShipIt auto-updater running as root | **Observed** | `phase2-onboard/all-claude-processes.txt` | `Squirrel.framework/Resources/ShipIt` process runs as `root`. Privilege escalation vector — auto-updater has root access. |

**Layer signal strength: 0.90** (strong: signed app, labeled Electron process tree, VM process is unique and high-signal)

### File / Artifact Layer

| IOC | Status | Evidence | Notes |
|---|---|---|---|
| `~/Library/Application Support/Claude/` Electron user-data-dir | **Observed** | `baseline/claude-desktop-dir.txt`, `phase1-install/app-support-breakdown.txt` | 10 GB total. Contains: `vm_bundles/` (9.6 GB), `local-agent-mode-sessions/` (9.2 MB), `Claude Extensions/`, `Cache/`, `Code Cache/`, Cookies, Preferences, Session Storage. |
| VM bundle at `vm_bundles/claudevm.bundle/` | **Observed** | `phase1-install/vm-bundles.txt`, `phase4-teardown/vm-persist-check.txt` | 10 GB `rootfs.img` (full Linux filesystem), 2.1 GB `rootfs.img.zst` (compressed), `efivars.fd`, `macAddress`, `machineIdentifier`, `vmIP`, `sessiondata.img` (45 MB). **Largest single artifact of any profiled tool.** Persists after quit. |
| `claude_desktop_config.json` with Cowork settings | **Observed** | `baseline/claude-desktop-config.txt`, `phase2-onboard/claude-config-running.txt` | Contains: `coworkWebSearchEnabled: true`, `coworkScheduledTasksEnabled: true`, `sidebarMode: "task"`, `localAgentModeTrustedFolders: ["/Users/echance/Documents/Claude Cowork"]`. Cowork-specific config keys distinguish from Claude Code. |
| Local agent mode session directories | **Observed** | `phase1-install/local-agent-sessions.txt`, `phase3a-basic/session-titles.txt` | `local-agent-mode-sessions/<folder-uuid>/<vm-uuid>/local_<session-uuid>.json` — 4 sessions found (110–114 KB each). Each contains: `sessionId`, `processName`, `vmProcessName`, `model`, `title`, `initialMessage`, `accountName`, `emailAddress`, `slashCommands` (15), `remoteMcpServersConfig` (2 MCP servers), `egressAllowedDomains` (22 domains), `systemPrompt` (42 KB). |
| Audit JSONL per session | **Observed** | `phase3a-basic/full-audit-log.jsonl`, `phase3b-agentic/calendar-full-audit.jsonl` | Complete audit trail with event types: `assistant`, `user`, `system`, `tool_use_summary`, `rate_limit_event`, `result`. Tool use summaries include natural-language descriptions of actions. 6–56 events per session. |
| `.claude/` state tree inside each session | **Observed** | `phase3a-basic/session-claude-dir.txt` | Full Claude Code state mirrored inside each session: `.claude.json`, `backups/`, `debug/` (72 KB debug log), `projects/<path>/session.jsonl` (33 KB transcript), `shell-snapshots/`, `todos/`, `session-env/`. Symlinks point to VM mount paths (`/sessions/<name>/mnt/.claude/`). |
| Desktop Extensions (DXT) with MCP servers | **Observed** | `phase1-install/chrome-control-manifest.txt`, `phase1-install/notes-manifest.txt` | Two extensions: `chrome-control` v0.1.5 (browser automation: execute JS, manage tabs, read pages via AppleScript), `notes` v0.1.7 (Apple Notes CRUD via macOS automation). Each has a Node.js MCP server entry point. |
| Skills plugin with document generation capabilities | **Observed** | `phase3c-selfmod/skills-manifest.txt`, `phase2-onboard/skills-plugin.txt` | 6 skills: `skill-creator`, `xlsx`, `pptx`, `pdf`, `docx`, `schedule`. Includes full Office XML schema files (ISO-IEC29500), Python scripts for document generation, and a skill evaluation framework. |
| Plugin marketplace (git clone) | **Observed** | `phase1-install/known-marketplaces.txt`, `phase3c-selfmod/marketplace-catalog.txt` | Git clone of `anthropics/knowledge-work-plugins`. 19+ plugins for enterprise departments (sales, finance, legal, marketing, engineering, HR, data, design, etc.) plus partner-built plugins (Slack by Salesforce, Apollo.io, Common Room). |
| Trusted folder configuration | **Observed** | `phase1-install/cowork-trusted-folder.txt` | `/Users/echance/Documents/Claude Cowork/` — empty. Configured in `claude_desktop_config.json` as `localAgentModeTrustedFolders`. |

**Layer signal strength: 0.95** (strongest of any tool: 10 GB VM image, rich session data, complete audit trails, DXT extensions, skills, marketplace)

### Network Layer

| IOC | Status | Evidence | Notes |
|---|---|---|---|
| Outbound TLS connections from Network utility process | **Observed** | `phase2-onboard/claude-network-post-launch.txt`, `phase2-onboard/dns-resolution.txt` | 15 connections from Claude Helper (Network) PID 37082. Destinations: `160.79.104.10` (Anthropic API), AWS EC2 instances (34.200.175.163, 18.97.36.61, 98.87.131.13), Google Cloud (34.36.57.103, 35.190.46.17), `fbcdn.net` (57.144.104.128). Mix of TCP ESTABLISHED and UDP (QUIC). |
| Persistent TLS connections (not ephemeral like Claude Code CLI) | **Observed** | `phase2-onboard/claude-network-post-launch.txt` | 5 concurrent TCP connections to Anthropic IP (160.79.104.10). Persistent during app session — attributable to PID at any polling interval. Similar to Cursor's persistent connection pattern, opposite of Claude Code CLI's ephemeral bursts. |
| VM network isolation with egress allowlist | **Observed** | `phase3a-basic/egress-domains.txt` | VM sandbox restricts outbound to 22 domains: package registries (npm, pypi, crates.io, yarn), `github.com`, Ubuntu repos, Playwright CDN, and `*.anthropic.com`/`*.claude.com`. This is a governance-relevant artifact — the tool self-reports its network boundary. |
| VM has dedicated IP on host-only network | **Observed** | `phase1-install/vm-ip.txt` | VM IP: `192.168.64.11`. VM MAC: `fa:2d:c5:58:59:86`. Operates on Apple Virtualization host-only network. VM-to-host traffic is local but may be observable via `vmnet` interface. |
| MCP connector network traffic (Google Calendar, Indeed) | **Architecture confirmed** | `phase3a-basic/session-json-structure.txt` | Session JSON lists 2 remote MCP servers: Google Calendar (9 tools) and Indeed (4 tools). Traffic would route through the desktop app's Network utility process (not the VM). |

**Layer signal strength: 0.80** (strong: persistent connections PID-attributable, VM egress allowlist is novel detection signal, multiple distinct destination IPs)

### Identity / Access Layer

| IOC | Status | Evidence | Notes |
|---|---|---|---|
| Account name and email in session JSON | **Observed** | `phase3a-basic/session-json-structure.txt` | `accountName: "Evan"`, `emailAddress: "evanlewischance@gmail.com"` — cleartext in every session JSON file. **Strongest identity signal of any profiled tool.** Unlike Claude Code (OAuth in backups), this is directly in the session metadata. |
| Code signing authority as provenance signal | **Observed** | `phase1-install/code-signing.txt` | `Developer ID Application: Anthropic PBC (Q6L2SF6YDW)`, TeamIdentifier `Q6L2SF6YDW`. Cryptographic binary attribution via Apple notarization chain. Identical authority to standalone Claude Code entitlement. |
| VM machine identifier | **Observed** | `phase1-install/vm-machine-id.txt` | Binary plist with UUID. Persists across sessions — serves as a device-level identity anchor for the VM. |
| Session UUIDs as correlation keys | **Observed** | `phase3a-basic/session-json-structure.txt` | Three correlated UUIDs per session: `sessionId` (local_<uuid>), `cliSessionId` (internal), `vmProcessName` (human-readable). Enable cross-artifact correlation of identity, file, and behavior evidence. |
| Remote MCP server credentials | **Architecture confirmed** | `phase3a-basic/session-json-structure.txt` | Google Calendar and Indeed MCP servers configured with UUIDs. Authentication state managed by desktop app. Credentials not directly visible in session JSON (managed by connector infrastructure). |

**Layer signal strength: 0.90** (strongest identity of any tool except OpenClaw: cleartext email in session data, code signing, VM identity, session correlation)

### Behavior Layer

| IOC | Status | Evidence | Notes |
|---|---|---|---|
| Autonomous multi-step task execution | **Observed** | `phase3b-agentic/calendar-audit-analysis.txt` | 56 audit events in calendar session. 5 tool_use_summary events showing multi-step agentic behavior: calendar retrieval, cross-account correlation, user preference collection, optimization. |
| Shell command execution within VM | **Observed** | `phase3a-basic/tool-use-events.txt` | "Install OpenClaw" session executed shell commands inside VM: architecture check, Homebrew install attempt, package availability checks. Tool use summaries confirm shell execution through audit trail. |
| Scheduled task creation capability | **Architecture confirmed** | `phase3c-selfmod/schedule-skill.txt` | `schedule` skill creates autonomous recurring tasks with cron expressions. Config `coworkScheduledTasksEnabled: true` enables this. Tasks run within the app process — not persistent daemon. |
| Self-modification via skill-creator | **Architecture confirmed** | `phase3c-selfmod/skills-manifest.txt` | `skill-creator` skill can create, modify, and benchmark new skills. Includes evaluation framework (`run_eval.py`, `run_loop.py`, `generate_report.py`). No approval gate for skill creation. |
| External service integration (MCP connectors) | **Observed** | `phase3a-basic/session-json-structure.txt`, `phase3b-agentic/calendar-audit-analysis.txt` | Google Calendar (9 tools: create/update/delete events, find meeting times, list calendars) and Indeed (4 tools) active as remote MCP servers. Claude executed calendar operations autonomously. |
| Browser automation via DXT extension | **Architecture confirmed** | `phase1-install/chrome-control-manifest.txt` | `chrome-control` extension: `execute_javascript`, `get_page_content`, `open_url`, tab management. Uses Chrome AppleScript API. **Novel cross-app automation capability.** |

**Layer signal strength: 0.85** (strong: shell execution in VM confirmed via audit trail, MCP connector activity confirmed, scheduled tasks and self-modification architecturally confirmed)

---

## 2. Confidence Score Calculation

### Using Default Five-Layer Weights

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.25      0.90               0.225
File / Artifact      0.15      0.95               0.1425
Network              0.15      0.80               0.120
Identity / Access    0.10      0.90               0.090
Behavior             0.15      0.85               0.1275
Binary Hash          0.20      1.00               0.200
                                          ──────────────
base_score                                         0.905
```

*Note: Binary hash = 1.00 because the signed app bundle at a known path with verified Anthropic code signing is the highest-confidence binary attribution possible.*

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (clean Electron tree)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard app install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard paths)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct connections)
[✗] Unresolved process-to-network linkage:       −0.10  → NOT APPLIED (Network utility centralizes)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (local macOS app)
[✗] Weak/missing identity correlation:           −0.10  → NOT APPLIED (cleartext email in sessions)
                                                 ──────
penalties                                         0.00
```

### Evasion Boost

```
No evasion indicators detected in this run.
evasion_boost                                     0.00
```

### Final Score

```
final_confidence = 0.905 - 0.00 + 0.00 = 0.905

Classification: High (≥0.75)
```

**Highest confidence score of any profiled tool.** Surpasses OpenClaw (0.80) and Cursor (0.79). Driven by the combination of signed app binary, massive file footprint, persistent network connections, cleartext identity, and rich behavioral audit trails.

### Proposed Tool-Specific Weights (Claude Cowork)

```
Layer                Default    Proposed    Rationale
Process / Execution  0.25       0.25        Multi-process Electron + VM = strong signal
File / Artifact      0.15       0.20        10 GB footprint is largest of any tool
Network              0.15       0.10        Persistent but centralized in one process
Identity / Access    0.10       0.15        Cleartext email is strongest identity signal
Behavior             0.15       0.10        Audit trail is strong but app-dependent
Binary Hash          0.20       0.20        Signed binary is highest-confidence anchor
```

Using proposed weights:

```
base_score = 0.25×0.90 + 0.20×0.95 + 0.10×0.80 + 0.15×0.90 + 0.10×0.85 + 0.20×1.00
           = 0.225 + 0.190 + 0.080 + 0.135 + 0.085 + 0.200 = 0.915

Classification: High (≥0.75)
```

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | High (0.905) |
| Tool Class | C (Autonomous Executor) — escalates from A in Cowork mode |
| Asset Sensitivity | Tier 0 (lab workspace, empty trusted folder) |
| Action Risk | R2 (file operations in VM sandbox, MCP connector activity) |
| Actor Trust | T2 (authenticated user account) |

**Applicable rules:**
- Rule 2: Medium+ confidence + Class C → **Approval Required**
- Rule 3: High confidence + R2 → **Approval Required**
- Note: R3 would apply if MCP connectors access sensitive external services

**Decision: Approval Required** (Rule 2 + Rule 3)

**Governance nuance:** The VM sandbox mitigates direct host risk (file operations isolated). However, MCP connectors (Google Calendar, Indeed) operate outside the VM through the desktop app — these represent the primary lateral risk surface. Scheduled task capability (`coworkScheduledTasksEnabled`) introduces proactive execution risk without full Class D persistence.

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-014
Date:                2026-03-05
Tool:                Claude Cowork (Claude Desktop v1.1.4498)
Scenario ID:         CW-POS-01 (Standard install + launch + session analysis + teardown)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — 12-process Electron architecture with labeled
                     helpers (Plugin, Renderer, GPU, Network). Apple
                     Virtualization.VirtualMachine XPC service hosts full Linux
                     VM. ShipIt auto-updater runs as root. 546 MB aggregate RSS.
                     Evidence: phase2-onboard/all-claude-processes.txt
  File/Artifact:     OBSERVED — 10 GB in ~/Library/Application Support/Claude/.
                     VM bundle (9.6 GB rootfs.img), local-agent-mode-sessions
                     with per-session audit.jsonl, .claude/ state tree, DXT
                     extensions, skills plugin with document generation, plugin
                     marketplace (19+ enterprise plugins). Largest file footprint
                     of any profiled tool.
                     Evidence: phase1-install/app-support-breakdown.txt,
                     phase3a-basic/full-audit-log.jsonl
  Network:           OBSERVED — 15 outbound TLS connections from Network utility
                     process. Persistent connections to Anthropic API, AWS, Google
                     Cloud. All PID-attributable at any polling interval. VM has
                     22-domain egress allowlist and dedicated IP (192.168.64.11).
                     Evidence: phase2-onboard/claude-network-post-launch.txt,
                     phase3a-basic/egress-domains.txt
  Identity:          OBSERVED — Cleartext accountName ("Evan") and emailAddress
                     ("evanlewischance@gmail.com") in every session JSON. Code
                     signing: Anthropic PBC (Q6L2SF6YDW). VM machineIdentifier
                     persists across sessions. Three-UUID session correlation.
                     Evidence: phase3a-basic/session-json-structure.txt,
                     phase1-install/code-signing.txt
  Behavior:          OBSERVED — Multi-step agentic execution confirmed via
                     audit.jsonl (56 events in calendar session, 34 in install
                     session). Shell execution in VM. MCP connector activity
                     (Google Calendar CRUD). Schedule skill and skill-creator
                     enable proactive and self-modification behavior.
                     Evidence: phase3b-agentic/calendar-audit-analysis.txt,
                     phase3a-basic/tool-use-events.txt

Confidence Result:   0.905 (High) — default weights
                     0.915 (High) — proposed calibrated weights
                     Highest confidence score of any profiled tool
Policy Decision:     Approval Required (Rule 2 + Rule 3)
Evidence Links:      113 files across 7 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           PASS
Residual Risk:       (1) Scheduled task execution not directly exercised —
                     architecture confirmed but runtime behavior untested.
                     (2) DXT browser automation (chrome-control) not exercised.
                     (3) Skill-creator self-modification not exercised.
                     (4) MCP connector data flow not traced end-to-end.
                     (5) Windows variant not tested.
```

---

## 5. Cross-Tool Comparison

| Dimension | Claude Cowork (CW-POS-01) | Cursor (CUR-POS-01) | Claude Code (CC-POS-01) |
|---|---|---|---|
| **Tool type** | Desktop app (Electron + VM) | Desktop IDE (Electron) | CLI tool (Node.js) |
| **Process count** | 12 (incl. VM XPC service) | 29 | 1–3 |
| **Memory footprint** | 546 MB | 2.1 GB | 59–84 MB |
| **Disk footprint** | 10 GB (VM images dominate) | 14 MB (`~/.cursor/`) | <1 MB (`~/.claude/`) |
| **VM isolation** | Full Linux VM (Virtualization.framework) | None (host-level sandbox) | None |
| **Identity signal** | Cleartext email in session JSON | Account state in Electron user-data-dir | OAuth profile in `~/.claude/backups/` |
| **Network pattern** | Persistent TLS (like Cursor) | Persistent TLS | Ephemeral HTTPS bursts |
| **Network attribution** | Network utility PID (trivial) | Extension-host PID (trivial) | Main process PID (hard to capture) |
| **Audit trail** | `audit.jsonl` per session (complete) | Agent transcript JSONL (complete) | Session JSONL in `~/.claude/projects/` |
| **Self-modification** | skill-creator + marketplace | None built-in | Plugin marketplace (on first launch) |
| **Scheduled tasks** | `schedule` skill + `coworkScheduledTasksEnabled` | None | None |
| **Persistence** | None (passive files only) | None (passive files only) | None (passive files only) |
| **Confidence** | 0.905 (High) | 0.79 (High) | 0.71 (Medium) |
| **Class** | C (Autonomous Executor) | A→C (escalation via agent-exec) | C (CLI agentic mode) |

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **Claude Cowork runs a full Linux VM via Apple Virtualization framework.** The `com.apple.Virtualization.VirtualMachine` XPC service hosts a 10 GB `rootfs.img` with dedicated MAC address, IP, and EFI boot. This is a fundamentally different execution model from any profiled tool — file operations occur inside the VM, not on the host. Detection must identify both the Electron app AND the VM process. The `com.apple.security.virtualization` entitlement in the app binary is the earliest detection signal. | Section 4 (new profile), Section 5 | Create new Section 4.x for Claude Cowork. Note VM-based execution model as novel IOC category. Consider whether VM-sandboxed tools warrant a distinct risk sub-classification within Class C. |
| 2 | **10 GB passive file footprint is the largest of any profiled tool.** The VM bundle alone is 9.6 GB. Combined with sessions, extensions, and plugins, the total is 10 GB. This dwarfs OpenClaw (215 MB), Cursor (14 MB), and Claude Code (<1 MB). Detection via disk space analysis is trivially achievable — a 10 GB `vm_bundles/` directory is an unmistakable signal. | Section 4 (new profile) | Add disk footprint as a detection signal. Note that `vm_bundles/claudevm.bundle/` is pathognomonic for Claude Cowork. |
| 3 | **Cleartext email and account name in every session JSON.** `accountName` and `emailAddress` fields appear in every `local_*.json` file under `local-agent-mode-sessions/`. This is the strongest identity signal of any profiled tool — stronger than Claude Code's OAuth backup JSON and Cursor's Electron user-data-dir. No extraction or parsing required — it's a top-level JSON field. | Section 4 (new profile), Appendix B | Add identity IOC. Recommend higher identity weight for Claude Cowork vs other tools. |
| 4 | **`coworkScheduledTasksEnabled` config enables proactive execution.** The `schedule` skill creates autonomous recurring tasks with cron expressions. Combined with the config flag, this represents a proactive execution capability that approaches Class D criteria. However, scheduled tasks only run while the app is open — they do not survive app quit (no LaunchAgent). This is "soft proactive" — proactive within a session, not persistent across reboots. | Section 5 (Class taxonomy), Section 4 (new profile) | Define "soft proactive" as a sub-criterion. Claude Cowork meets 2 of 4 Class D criteria: (1) proactive/scheduled execution (while running), (2) self-modification (skill-creator). It lacks: (3) daemon persistence, (4) external communication channels beyond MCP connectors. Classify as C+ or note D-adjacent characteristics. |
| 5 | **VM egress allowlist is a governance-relevant artifact.** The VM sandbox restricts outbound traffic to 22 domains (package registries, GitHub, Ubuntu repos, Anthropic/Claude). This allowlist is embedded in every session JSON as `egressAllowedDomains`. The tool self-reports its own network boundary — a novel compliance signal. Monitoring changes to this allowlist across versions would detect capability expansion. | Section 4 (new profile), Section 7 | Add egress allowlist as a compliance IOC. Note that the allowlist may change between app versions — version-tracking the allowlist is recommended. |
| 6 | **DXT extensions enable cross-app automation via AppleScript.** `chrome-control` extension can execute JavaScript in Chrome tabs, read page content, and manage tabs. `notes` extension can CRUD Apple Notes. Both use AppleScript APIs running on the host (outside the VM). This means Cowork can interact with other applications on the host while its primary file operations are VM-isolated. The host attack surface is the DXT extension layer, not the file system. | Section 4 (new profile), Section 7 | Add DXT extensions as behavioral IOC. Note the split attack surface: file operations in VM (sandboxed), AppleScript operations on host (not sandboxed). Browser automation + Apple Notes access represents a cross-application lateral movement capability. |
| 7 | **ShipIt auto-updater runs as root.** The Squirrel.framework `ShipIt` process executes as root for auto-updates. This is a privilege escalation vector — the update mechanism has higher privileges than the app itself. This pattern exists in many Electron apps but is governance-relevant for an autonomous agent tool. | Section 4 (new profile), Section 7 | Note root auto-updater as a privilege concern. Recommend monitoring auto-update events for unexpected binary changes. |
| 8 | **Plugin marketplace creates a dynamic capability surface.** The `anthropics/knowledge-work-plugins` git clone provides 19+ enterprise plugins that can be enabled/disabled. Combined with `skill-creator` and `cowork-plugin-management`, this means the tool's capability set is mutable at runtime without app reinstallation. Detection profiles must account for capability expansion through plugin installation. | Section 4 (new profile), Section 5 | Add marketplace plugin inventory as a capability assessment IOC. Periodic marketplace scanning recommended to detect new plugin installations. |
| 9 | **Claude Cowork shares file artifacts with Claude Code.** Both use `~/.claude/` for CLI state. The Cowork sessions create `.claude/` state trees INSIDE each session that mirror the Claude Code structure (backups, debug, projects, todos). Detection rules for Claude Code file artifacts will also match inside Cowork session directories — creating cross-tool signal aliasing. | Section 4.1 (Claude Code), Section 4 (new Cowork profile) | Add cross-reference. Note that `~/.claude/` is shared between Claude Code CLI and Claude Desktop app. Session-internal `.claude/` trees should be attributed to Cowork, not standalone Claude Code. |
| 10 | **Feature flags in process arguments reveal internal codenames.** The `--desktop-features` JSON in renderer process args includes: `ccdPlugins`, `chillingSlothFeat`, `chillingSlothLocal`, `yukonSilver`, `yukonSilverGems`, `plushRaccoon` (unavailable), `quietPenguin` (unavailable). These internal codenames can be used for version fingerprinting and feature prediction — similar to Copilot's A/B experiment flags. | Section 4 (new profile) | Add feature flag fingerprinting as a version/capability detection signal. Monitor `plushRaccoon` and `quietPenguin` — currently unavailable features that may represent upcoming capabilities. |

---

## 7. Proposed Weight Adjustment

| Layer | Default Weight | Proposed Cowork Weight | Justification |
|---|---|---|---|
| Process | 0.25 | 0.25 | Multi-process Electron + VM is strong and unique. No change needed. |
| File | 0.15 | 0.20 | 10 GB footprint is unmistakable. Upgrade from default. |
| Network | 0.15 | 0.10 | Persistent but centralized in one process. Less forensically complex than distributed network patterns. |
| Identity | 0.10 | 0.15 | Cleartext email is the strongest identity signal of any tool. Upgrade. |
| Behavior | 0.15 | 0.10 | Audit trail is strong but depends on session existence. Downgrade slightly. |
| Binary Hash | 0.20 | 0.20 | Signed binary is definitive. No change. |

---

## 8. Summary

LAB-RUN-014 is the first empirical validation of Claude Cowork. It reveals a **fundamentally different execution architecture** from any previously profiled tool.

**What's unique about Claude Cowork:**
- **VM-based sandboxed execution** via Apple Virtualization framework — file operations happen inside a full Linux VM, not on the host
- **10 GB passive footprint** — the largest of any profiled tool, dominated by the VM root filesystem image
- **Cleartext identity** in every session JSON — account name and email with zero extraction effort
- **Scheduled task capability** — approaches Class D proactive behavior without daemon persistence
- **Cross-app automation** — DXT extensions control Chrome and Apple Notes on the host while file operations are VM-isolated
- **Plugin marketplace** with 19+ enterprise plugins creates a dynamic, mutable capability surface
- **0.905 confidence score** — the highest of any profiled tool, driven by signed binary, massive footprint, and rich audit trails

**What's similar to other tools:**
- Electron multi-process architecture (like Cursor)
- Persistent TLS connections attributable to PID (like Cursor, unlike Claude Code)
- Session-level audit trails (like Cursor's agent transcripts, Claude Code's session JSONL)
- No active persistence mechanisms (like Cursor and Claude Code — no LaunchAgents, no crontab)
- Code-signed by Anthropic PBC (same authority as Claude Code)
- Shares `~/.claude/` state directory with Claude Code CLI

**Key governance takeaway:** Claude Cowork's VM isolation changes the risk calculus for file operations — the host filesystem is protected by the VM boundary. However, the DXT extension layer (browser automation, Apple Notes) and MCP connectors (Google Calendar, Indeed) operate outside the VM on the host, creating a split attack surface. Governance must monitor both the VM-isolated session activity AND the host-level DXT/MCP activity. The scheduled task capability, combined with skill-creator self-modification, makes this tool D-adjacent despite lacking daemon persistence.
