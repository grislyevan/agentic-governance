# LAB-RUN-005 Results: GitHub Copilot Installation & Runtime Telemetry

**Run ID:** LAB-RUN-005  
**Date:** 2026-03-02  
**Tool:** GitHub Copilot (github.copilot-chat v0.37.9) inside VS Code 1.109.5  
**Scenario ID:** CP-POS-01 (Standard VS Code session + Copilot extension install + launch)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/copilot-lab/LAB-RUN-005/` (91 files, SHA-256 hashed per phase)

**Authentication State:** GitHub account NOT authenticated during this run. Copilot extension was installed and loaded but operated in an unauthenticated/inactive state. This captures the "pre-auth" detection surface — all signals observable without an active Copilot subscription session.

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.3) | Status | Evidence | Notes |
|---|---|---|---|
| IDE host process (VS Code) + Copilot extension host subprocess | **Observed** | `phase2-launch/vscode-process-tree.txt`, `phase2-launch/vscode-copilot-processes.txt` | VS Code main (Electron PID 84519) → Code Helper (GPU PID 84538) → Code Helper (Network PID 84539) → Code Helper (Renderer PID 84550) → Code Helper (Plugin PID 84583, the extension host) → Code Helper (Node PIDs 84593, 84594) → Code Helper (Renderer PID 85201). 9 child processes total. The Plugin helper (`Code Helper (Plugin)`) is the extension host that loads Copilot. Process lineage is unambiguous — all processes are children of the VS Code Electron main process at `/Applications/Visual Studio Code.app/`. |
| Extension-host activity tied to chat/agent-style workflows | **Observed differently** | `phase3b-chat/copilot-log-contents.txt` | Copilot-related A/B experiment flags were queried on startup (`dwcopilot`, `copilot_t_ci`, `chat`, `edit_mode_hidden`, `use-responses-api`). The extension host loaded the Copilot extension, but no chat/agent workflows were exercised because GitHub auth was not completed (0 sessions). The entitlement check returned `chatEntitlement: 1, chatRegistered: 0` — the extension recognized Copilot capability but could not activate without authentication. |

**Layer signal strength: 0.80** (Strong process identification. VS Code + extension host tree is clear and well-structured. The Plugin helper subprocess is the key anchor for extension-level detection. However, the process names are generic — "Code Helper (Plugin)" is shared by ALL VS Code extensions, making Copilot-specific attribution dependent on additional layers.)

### File / Artifact Layer

| IOC (Playbook Section 4.3) | Status | Evidence | Notes |
|---|---|---|---|
| Copilot extension install manifests (`extensions/GitHub.copilot*`) | **Observed** | `phase1-install/copilot-extension-files.txt`, `phase1-install/copilot-extension-manifests.txt` | Extension directory at `~/.vscode/extensions/github.copilot-chat-0.37.9/` containing 242 files. Includes `package.json` with extension metadata, `dist/` directory with bundled JavaScript, and language-specific assets. Note: directory uses **lowercase** `github.copilot-chat`, not `GitHub.copilot` — the playbook should update the case convention. |
| Workspace extension settings, policy files, local logs/caches | **Observed** | `phase2-launch/copilot-state-files.txt`, `phase4-teardown/copilot-persistent-artifacts.txt` | Cached extension VSIX at `~/Library/Application Support/Code/CachedExtensionVSIXs/github.copilot-chat-0.37.9`. VS Code logs directory at `~/Library/Application Support/Code/logs/20260302T150456/` contains session-specific log files including `vscode.github-authentication/GitHub Authentication.log` — records the auth check (0 sessions found). Extension state persists across VS Code restarts in `~/Library/Application Support/Code/`. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| VS Code `machineId` as device fingerprint | `phase3b-chat/copilot-log-contents.txt` | Telemetry log contains `common.machineId: 289de1161938b128cbe20159b9210e0da084f58dcf5483984d7d57cbeca1f77a` — a persistent SHA-256 device identifier that survives reinstalls. Stronger than OS-level identity for device correlation. |
| `devDeviceId` as secondary identifier | `phase3b-chat/copilot-log-contents.txt` | UUID `e960111d-c649-4d1e-96e6-6ecadd0748aa` is another device-level identifier that persists across sessions. Combined with `machineId`, provides dual device attribution. |
| Session ID for cross-artifact correlation | `phase3b-chat/copilot-log-contents.txt` | Session UUID `29d03f6a-8cd0-40a7-b0fb-28146793bb431772489097531` links all telemetry events within a single VS Code session. Analogous to Claude Code's session UUID. |
| A/B experiment flag cache | `phase3b-chat/copilot-log-contents.txt` | `abexp.assignmentcontext` field contains internal experiment flag identifiers including `dwcopilot:31170013`, `copilot_t_ci:31333650`, `chat:31457767`, `edit_mode_hidden:31461530`. Reveals product feature state and can be used for version fingerprinting. |
| GitHub Authentication log as auth-state evidence | `phase3b-chat/github-auth-log.txt` | `GitHub Authentication.log` records `Got 0 sessions` — explicit evidence that no GitHub account is authenticated. This log's *absence* of sessions is itself a governance-relevant signal: Copilot installed but unused (policy gap) or Copilot installed with personal account not yet authenticated. |
| Copilot installed as `github.copilot-chat` (bundled) | `phase1-install/copilot-extension-install.txt` | Installing `GitHub.copilot` actually installs `github.copilot-chat` — the extensions have been merged. The playbook's IOC listing `GitHub.copilot*` should note this bundling. Extension detection should look for `github.copilot-chat*` in the extension directory. |

**Layer signal strength: 0.85** (Strong, distinctive artifacts. Extension directory is unique to Copilot. Telemetry logs contain rich device and session identifiers. VS Code's Application Support directory provides persistent state. The file footprint is smaller than Claude Code's 308 files but larger than Ollama's 13 files.)

### Network Layer

| IOC (Playbook Section 4.3) | Status | Evidence | Notes |
|---|---|---|---|
| Traffic to `copilot-proxy.githubusercontent.com`, GitHub Copilot API endpoints | **Observed (indirect)** | `phase2-launch/vscode-network-connections.txt` | 15 active HTTPS connections from Code Helper (Network PID 84539) to multiple IP addresses: `13.107.5.93:443`, `13.107.226.66:443`, `104.208.16.91:443`, `13.107.213.70:443`, `13.107.246.70:443`, `23.222.27.132:443`, `150.171.73.16:443`, `150.171.74.16:443`. Without TLS/SNI inspection, specific hostname attribution is not possible, but the IP ranges are consistent with Microsoft/GitHub CDN infrastructure. Connections were **persistent** (ESTABLISHED state), unlike Claude Code's ephemeral HTTPS bursts. |
| Burst timing aligned with suggestion/chat activity | **Not observed** | N/A | No suggestion or chat activity occurred (unauthenticated). The network connections observed are VS Code's baseline telemetry and update-check traffic, not Copilot inference traffic. |

**Additional network findings:**

| Finding | Evidence | Significance |
|---|---|---|
| VS Code Network Service is a dedicated process with all connections | `phase2-launch/vscode-network-connections.txt` | All 15 network connections belong to PID 84539 (`Code Helper` with `network.mojom.NetworkService`). This is a **centralized** network architecture — unlike Claude Code (where the main process makes connections) or Ollama (where the daemon listens on localhost). Process-to-socket attribution is clean and trivial via `lsof` because the Network Service helper is a persistent, identifiable process. |
| Persistent ESTABLISHED connections (unlike Claude Code's ephemeral HTTPS) | `phase2-launch/vscode-network-connections.txt` | Connections remain in ESTABLISHED state across polling intervals. This inverts the network detection difficulty observed with Claude Code — VS Code/Copilot's connections are long-lived and easily captured at any polling interval. |
| Crashpad URL reveals telemetry endpoint | `phase2-launch/vscode-copilot-processes.txt` | Process args contain `--url=appcenter://code?aid=be71415d-3893-4ae5-b453-e537b9668a10` — confirms Microsoft AppCenter telemetry integration. This is a process-visible network indicator (no traffic capture needed). |

**Layer signal strength: 0.55** (Network connections are present and easily attributable to VS Code's dedicated Network Service process. However, without TLS/SNI inspection, we cannot confirm specific Copilot endpoints vs general VS Code telemetry. No Copilot-specific inference traffic was generated due to unauthenticated state. Score reflects instrumentation gap rather than architectural weakness.)

### Identity / Access Layer

| IOC (Playbook Section 4.3) | Status | Evidence | Notes |
|---|---|---|---|
| GitHub account auth state (org-managed vs personal) | **Observed (negative)** | `phase3b-chat/github-auth-log.txt`, `phase2-launch/github-keychain-check.txt` | GitHub Authentication log explicitly records `Got 0 sessions` across 5 checks at launch. macOS Keychain lookup for `vscodevscode.github-authentication` returned "specified item could not be found." This confirms: **no GitHub account is authenticated**. This negative signal is itself a governance finding — Copilot is *installed* but *not authenticated*, meaning either (a) the tool is dormant, or (b) the user has not yet completed the auth flow. |
| License/entitlement context from org policy | **Observed (partial)** | `phase3b-chat/copilot-log-contents.txt` | Telemetry shows `chatEntitlement: 1` (VS Code recognizes Copilot capability at the IDE level) but `chatRegistered: 0` (no active Copilot registration/subscription linked). This entitlement check is a **critical governance signal** — it distinguishes "Copilot installed + entitled" from "Copilot installed + not entitled." |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| `machineId` as persistent device identity | `phase3b-chat/copilot-log-contents.txt` | SHA-256 `machineId` (`289de116...`) is a VS Code-generated device fingerprint that persists across sessions and reinstalls. Stronger than OS-level process ownership for device-level attribution. Equivalent to Ollama's ed25519 keypair but derived differently. |
| `devDeviceId` as secondary device ID | `phase3b-chat/copilot-log-contents.txt` | UUID `e960111d-c649-4d1e-96e6-6ecadd0748aa` provides a second device-level identifier. Two independent device IDs provide robust device correlation. |
| `firstSessionDate` and `lastSessionDate` reveal usage history | `phase3b-chat/copilot-log-contents.txt` | `firstSessionDate: Fri, 10 Jan 2025` and `lastSessionDate: Thu, 12 Feb 2026` — these are VS Code session dates (not Copilot-specific) but reveal the endpoint's usage history with VS Code. |
| No GitHub account profile stored locally (unlike Claude Code's OAuth store) | `phase2-launch/github-keychain-check.txt` | Unlike Claude Code which stores full OAuth profiles (email, org UUID, role) in `~/.claude/backups/`, Copilot's GitHub auth state is managed through VS Code's built-in GitHub Authentication extension and macOS Keychain. When not authenticated, zero identity artifacts exist on disk. |

**Layer signal strength: 0.40** (Identity is the **defining governance layer** for Copilot per the playbook, but in this unauthenticated state, identity signals are limited to device-level identifiers. The explicit "0 sessions" auth state is itself a signal. In an authenticated state with an org-managed GitHub account, this layer would be the strongest — estimated 0.90+ — but cannot be empirically validated in this run. The low score here is a scenario limitation, not an architectural weakness.)

### Behavior Layer

| IOC (Playbook Section 4.3) | Status | Evidence | Notes |
|---|---|---|---|
| Suggestion acceptance cadence + rapid edit bursts | **Not observed** | N/A | No Copilot suggestions were generated (unauthenticated). This behavioral IOC requires an active Copilot session to validate. |
| AI-chat-to-edit sequences across multiple files | **Not observed** | N/A | No chat interactions occurred (unauthenticated). |
| High-volume generated changes without normal review cadence | **Not observed** | N/A | No AI-generated changes occurred. |

**Additional behavioral findings:**

| Finding | Evidence | Significance |
|---|---|---|
| Telemetry feature flag queries as behavioral fingerprint | `phase3b-chat/copilot-log-contents.txt` | VS Code queried 45+ experiment features on startup, including Copilot-specific flags (`dwcopilot`, `copilot_t_ci`, inline suggestions, chat editing). The *act of querying* these flags — even without an active Copilot session — is itself a behavioral signal: it indicates Copilot is installed and VS Code is checking for its availability. This is a "passive behavioral" signal. |
| Extension activation telemetry | `phase3b-chat/copilot-log-contents.txt` | `telemetry/activatePlugin` events fired for built-in extensions. The Copilot extension's activation (or lack thereof due to missing auth) would be logged here — providing evidence of tool presence even without active usage. |

**Layer signal strength: 0.25** (No active Copilot behavioral signals were generated because the tool was unauthenticated. The passive behavioral signals — feature flag queries, extension activation — provide weak but non-zero behavioral evidence. In an authenticated, active session, this layer would be estimated 0.70+ based on suggestion cadence and chat interaction patterns.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.80               0.240
File / Artifact      0.20      0.85               0.170
Network              0.15      0.55               0.083
Identity / Access    0.15      0.40               0.060
Behavior             0.20      0.25               0.050
                                          ──────────────
base_score                                         0.603
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (clear Electron → helper chain)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard VS Code install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.vscode/, ~/Library/Application Support/Code/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct connection)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Connections attributed to VS Code Network Service PID, but specific Copilot endpoints
     not confirmed without TLS/SNI inspection)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[△] Weak/missing identity correlation:           −0.10  → PARTIAL: −0.05
    (Device IDs present, but GitHub account auth not completed — scenario limitation)
[△] Extension-host indistinguishable from others: −0.05 → APPLIED: −0.05
    (Code Helper (Plugin) hosts ALL extensions; Copilot-specific process attribution
     requires file-layer or network-layer cross-correlation)
                                                 ──────
penalties                                         0.15
```

### Final Score

```
final_confidence = 0.603 - 0.15 = 0.45

Classification: Medium (0.45 ≤ 0.45 < 0.75) — Barely Medium
```

### Score Assessment

The barely-Medium classification is **appropriate for this unauthenticated scenario.** The score is depressed by two factors:

1. **No active behavioral signals** — the behavior layer scored 0.25 (vs 0.75+ for Claude Code and 0.80 for Ollama) because Copilot wasn't actively generating suggestions or chat responses.
2. **Incomplete identity** — the identity layer scored 0.40 (vs 0.80 for Claude Code and 0.50 for Ollama) because GitHub auth wasn't completed.

Both are scenario limitations, not tool characteristics. In an authenticated, active session:

**Projected score with authentication + active usage:**

```
Layer                Weight    Signal Strength    Weighted
Process              0.30      0.80               0.240
File                 0.20      0.85               0.170
Network              0.15      0.70               0.105    (Copilot endpoints confirmed with TLS)
Identity             0.15      0.90               0.135    (GitHub org account verified)
Behavior             0.20      0.70               0.140    (Suggestion cadence + chat patterns)
                                          ──────────────
base_score                                         0.790
penalties                                         0.05     (extension-host ambiguity only)
final_confidence                                  0.740

Classification: Medium (0.45 ≤ 0.74 < 0.75) — Upper Medium, near High threshold
```

**Projected with EDR-grade telemetry + org auth:**  ~0.80 (High)

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | Medium (0.45) |
| Tool Class | A (SaaS Copilot / Assistive IDE Feature) |
| Asset Sensitivity | Tier 0 (home directory, test workspace) |
| Action Risk | R1 (extension installed, no active AI usage) |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Rule 1: Medium confidence + Tier 0 + R1 → **Detect**
- Per Section 5.1 Class A default posture: "Detect/Warn baseline → Approval Required for sensitive scope"

**Decision: Detect** — extension presence detected, no active usage in this session.

In an authenticated, active scenario with org-managed account:
- Medium confidence + Tier 1/2 + R2 → **Warn** (for suggestion acceptance activity)
- If personal account detected on managed endpoint → **Warn with step-up to Approval Required**

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-005
Date:                2026-03-02
Tool:                GitHub Copilot (github.copilot-chat v0.37.9) in VS Code 1.109.5
Scenario ID:         CP-POS-01 (Standard VS Code session + Copilot install + launch)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive (unauthenticated baseline)

Signal Observations:
  Process:           OBSERVED — VS Code Electron main (PID 84519) with 9 child
                     processes including Code Helper (Plugin) extension host.
                     Clear, unambiguous process tree from /Applications/Visual
                     Studio Code.app/. Evidence: phase2-launch/vscode-process-tree.txt
  File/Artifact:     OBSERVED — ~/.vscode/extensions/github.copilot-chat-0.37.9/
                     with 242 files. Cached VSIX in ~/Library/Application Support/Code/.
                     Telemetry logs with machineId, devDeviceId, session UUID.
                     Evidence: phase1-install/copilot-extension-files.txt,
                     phase3b-chat/copilot-log-contents.txt
  Network:           PARTIALLY OBSERVED — 15 persistent HTTPS connections from VS Code
                     Network Service helper to Microsoft/GitHub IPs. Process-to-socket
                     attribution clean. Specific Copilot endpoints not confirmed
                     without TLS/SNI inspection. Evidence: phase2-launch/
                     vscode-network-connections.txt
  Identity:          PARTIALLY OBSERVED — GitHub auth state: 0 sessions (not
                     authenticated). machineId and devDeviceId provide device-level
                     identity. No org/account context (auth not completed).
                     Evidence: phase3b-chat/github-auth-log.txt,
                     phase2-launch/github-keychain-check.txt
  Behavior:          MINIMALLY OBSERVED — No active Copilot suggestions or chat.
                     Passive behavioral signals only: A/B experiment flag queries
                     for Copilot features on startup. Evidence: phase3b-chat/
                     copilot-log-contents.txt

Confidence Result:   0.45 (Medium, barely) — five-layer model
                     Projected with auth + active usage: ~0.74 (Medium, upper)
                     Projected with EDR + org auth: ~0.80 (High)
Policy Decision:     Detect (Rule 1, Section 6.3; Class A default posture)
Evidence Links:      91 files across 7 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Identity layer untested with authenticated GitHub account;
                     behavioral layer untested with active suggestions/chat;
                     network layer needs TLS/SNI for endpoint confirmation;
                     extension-host process is shared by all extensions
```

---

## 5. Class A-Specific Analysis

| Question | Finding |
|---|---|
| Does the extension run as a subprocess of the VS Code extension host? | **Yes.** The Copilot extension loads inside the `Code Helper (Plugin)` process (PID 84583), which is the VS Code extension host. This is a node.js process (`utility-sub-type=node.mojom.NodeService`) that runs all extensions in the same process context. There is no separate "Copilot process" — it shares the extension host with all other extensions. |
| What is the full process tree: VS Code → extension host → Copilot? | **Electron (84519) → Code Helper GPU (84538) → Code Helper Network (84539) → Code Helper Renderer (84550) → Code Helper Plugin/ExtHost (84583) → Code Helper Node×2 (84593, 84594) → Code Helper Renderer (85201).** The Plugin helper is the extension host where Copilot runs. 9 child processes total. |
| Does Copilot create any persistent files outside `~/.vscode/`? | **Yes.** `~/Library/Application Support/Code/CachedExtensionVSIXs/github.copilot-chat-0.37.9` stores the cached extension package. VS Code logs in `~/Library/Application Support/Code/logs/` contain Copilot-related entries. VS Code telemetry contains Copilot experiment flags. All three locations are outside `~/.vscode/`. |
| What GitHub auth state is stored locally? Where? | **None in this unauthenticated run.** When authenticated, GitHub tokens are stored in macOS Keychain under `vscodevscode.github-authentication`. The `GitHub Authentication.log` in VS Code's log directory records auth attempts and session state. |
| Can we distinguish org-managed vs personal GitHub accounts from artifacts? | **Not tested (unauthenticated).** The entitlement check (`chatEntitlement: 1, chatRegistered: 0`) suggests the infrastructure exists to distinguish account types, but we cannot confirm without an authenticated session. This is the highest-priority gap for CP-POS-02. |
| Does Copilot make network connections only to GitHub-owned endpoints? | **Partially confirmed.** Network connections went to IPs in Microsoft/GitHub ranges (13.107.x.x, 150.171.x.x, 23.222.x.x, 104.208.x.x). Without TLS/SNI, we cannot confirm Copilot-specific endpoints vs general VS Code telemetry. The Crashpad URL in process args confirms Microsoft AppCenter telemetry. |
| Does Copilot stay Class A or can it escalate to Class C (agent mode)? | **VS Code 1.109.5 includes agent/edit mode capabilities** (experiment flags `edit_mode_hidden`, `use-responses-api`, `chat` were all queried). However, these are gated behind authentication and feature flags. Without auth, agent mode cannot activate. When available, Copilot's agent mode would represent a Class A→C escalation path similar to Cursor — this needs validation in CP-POS-02 or CP-POS-03. |
| What is the network connection pattern during suggestion vs chat? | **Not observed (unauthenticated).** The 15 connections seen are VS Code's baseline telemetry traffic. Copilot suggestion traffic would be additional connections to `copilot-proxy.githubusercontent.com` — this needs validation in an authenticated session. |

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **Copilot extension is now bundled as `github.copilot-chat`, not separate `GitHub.copilot` + `GitHub.copilot-chat`.** Installing `GitHub.copilot` actually installs `github.copilot-chat` v0.37.9. The extension directory uses lowercase. | Section 4.3 File IOC | Update IOC: extension manifests are `github.copilot-chat-*` (lowercase, single extension). Remove reference to separate `GitHub.copilot` and `GitHub.copilot-chat` extensions. |
| 2 | **Process detection for Copilot requires cross-layer correlation.** The extension host process (`Code Helper (Plugin)`) hosts ALL VS Code extensions, not just Copilot. Process-layer detection alone cannot attribute activity to Copilot specifically — it requires file-layer (extension directory check) or network-layer (Copilot endpoint traffic) correlation. | Section 4.3 Process IOC | Add note: "Extension host process is shared by all extensions. Copilot-specific attribution requires cross-layer correlation with file artifacts (extension directory) or network endpoints (Copilot API traffic)." Recommend new penalty: "Extension-host process indistinguishable from other extensions: −0.05" |
| 3 | **VS Code `machineId` is a strong device identity signal — stronger than OS process ownership.** The SHA-256 `machineId` persists across sessions and reinstalls, providing robust device fingerprinting. Combined with `devDeviceId` (UUID), this gives dual device-level attribution. | Section 4.3 Identity IOC (new) | Add IOC: "VS Code `machineId` (SHA-256 device fingerprint) and `devDeviceId` (UUID) in telemetry logs — persistent device-level identity signals. Present even without GitHub authentication." |
| 4 | **GitHub Authentication log records auth state explicitly.** `GitHub Authentication.log` records "Got 0 sessions" when unauthenticated. This log's *absence* of sessions is a governance-relevant signal: Copilot is installed but either dormant or using a personal account not yet authenticated. | Section 4.3 Identity IOC (new) | Add IOC: "GitHub Authentication log (`vscode.github-authentication/GitHub Authentication.log`) records explicit auth state — session count, account type. Absence of sessions indicates installed-but-dormant state." |
| 5 | **A/B experiment flags reveal Copilot feature state and version.** The `abexp.assignmentcontext` field contains 30+ experiment flag IDs including `dwcopilot:31170013` and `copilot_t_ci:31333650`. This enables version fingerprinting and feature-state detection without inspecting extension files. | Section 4.3 File IOC (new) | Add IOC: "VS Code telemetry A/B experiment flags including `dwcopilot` and `copilot_t_ci` — reveals Copilot feature state and can be used for version fingerprinting." |
| 6 | **VS Code's Network Service is a centralized, persistent process for all connections.** Unlike Claude Code (short-lived HTTPS from main process) or Ollama (dedicated localhost listener), VS Code uses a dedicated `Code Helper` with `network.mojom.NetworkService` for all network I/O. This makes process-to-socket attribution trivial — all connections are on a single, identifiable PID. | Section 4.3 Network IOC | Add detail: "All VS Code network traffic flows through a dedicated Network Service helper process. Process-to-socket attribution is trivial via `lsof` — look for `Code Helper` with `NetworkService` type." |
| 7 | **`chatEntitlement` vs `chatRegistered` distinguish installation from activation.** The telemetry field `chatEntitlement: 1, chatRegistered: 0` distinguishes three states: (a) Copilot not installed (`chatEntitlement: 0`), (b) Copilot installed but not authenticated (`chatEntitlement: 1, chatRegistered: 0`), (c) Copilot active (`chatEntitlement: 1, chatRegistered: 1`). | Section 4.3 Identity IOC (new) | Add IOC: "`chatEntitlement` and `chatRegistered` fields in VS Code telemetry — distinguish installed/entitled/active states for Copilot." |
| 8 | **Identity is the strongest governance lever for Copilot, but weakest without auth.** When authenticated (org-managed GitHub account), identity would be the highest-confidence layer (~0.90). When unauthenticated, it's the weakest (0.40). This creates a bimodal distribution that differs fundamentally from Claude Code (identity always strong via OAuth) and Ollama (identity always weak, no accounts). | Section 4.3, Appendix B | Document the bimodal identity profile for Class A tools: "Identity layer is bimodal — strongest when authenticated (org-managed account), weakest when not. Weight should be context-dependent: 0.25 for authenticated Copilot, 0.10 for unauthenticated." |
| 9 | **VS Code/Copilot's network connections are persistent (ESTABLISHED), not ephemeral.** Unlike Claude Code's short-lived HTTPS bursts that evade polling, VS Code maintains long-lived connections that are trivially detectable at any polling interval. This inverts the network detection difficulty — similar to Ollama's persistent localhost listener but for outbound HTTPS. | Section 4.3 Network IOC, Appendix B | Document that network detection difficulty for Class A IDE extensions is low (persistent connections) — closer to Class B (Ollama's listener) than Class C (Claude Code's bursts). |
| 10 | **Copilot agent mode capabilities exist in VS Code 1.109.5 but are gated.** Experiment flags (`edit_mode_hidden`, `use-responses-api`, `chat`) indicate agent/edit mode is a VS Code feature gated behind Copilot auth and feature flags. This represents a potential Class A→C escalation path that needs validation. | Section 4.3, Section 5.1 | Add note to Class A: "Copilot's agent mode (when available) may escalate Copilot toward Class C behavior. Experiment flag `edit_mode_hidden` and `use-responses-api` indicate the capability exists. Classification should be re-evaluated when agent mode is exercised (CP-POS-03)." |

---

## 7. Proposed Layer Weight Calibration for Copilot (Class A)

Based on empirical observations, the default five-layer weights should be adjusted for Copilot/Class A tools:

### Unauthenticated Scenario (this run)

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Extension host is shared by all extensions — Copilot-specific attribution requires cross-layer correlation. Less distinctive than standalone processes. |
| File | 0.20 | 0.25 | Extension directory and VS Code logs are strong, unique artifacts. Telemetry logs contain rich device/session identifiers. |
| Network | 0.15 | 0.15 | No change — persistent connections are easy to detect, but endpoint attribution needs TLS/SNI. |
| Identity | 0.15 | 0.15 | No change for default. Identity is bimodal — see below. |
| Behavior | 0.20 | 0.20 | No change — behavioral signals should be strong when Copilot is active. |

### Authenticated Scenario (projected)

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.20 | De-emphasize — process signals are least Copilot-specific. |
| File | 0.20 | 0.20 | No change — solid but not dominant. |
| Network | 0.15 | 0.15 | No change. |
| Identity | 0.15 | 0.25 | **Increase significantly.** GitHub account state (org-managed vs personal) is the primary governance lever for Class A tools. This is the inverse of Ollama (where identity was reduced to 0.10). |
| Behavior | 0.20 | 0.20 | No change. |

---

## 8. Cross-Tool Comparison

| Layer | Claude Code (Class C) | Ollama (Class B) | Copilot (Class A) | Interpretation |
|---|---|---|---|---|
| Process | 0.85 | 0.90 | 0.80 | Copilot's extension-host process is slightly harder to attribute (shared by all extensions) |
| File | 0.95 | 0.90 | 0.85 | Copilot's footprint (242 files) is smaller than Claude Code (308) and larger than Ollama (13) |
| Network | 0.30 | 0.70 | 0.55 | Copilot's persistent connections are more detectable than Claude Code's HTTPS bursts, but less distinctive than Ollama's localhost:11434 |
| Identity | 0.80 | 0.50 | 0.40* | *Scenario-limited — projected 0.90 when authenticated. Bimodal distribution unique to Class A. |
| Behavior | 0.75 | 0.80 | 0.25* | *Scenario-limited — projected 0.70+ with active suggestions/chat. |
| **Final** | **0.71** | **0.69** | **0.45** | Lower score reflects unauthenticated scenario, not tool weakness. |

**Key insight:** Class A tools have a **bimodal detection profile** driven by authentication state. When authenticated with org-managed accounts, they score High on identity (the primary governance lever). When unauthenticated, they score low across identity and behavior, producing a misleadingly low overall confidence. Weight calibration should account for this bimodality.

**Milestone:** With LAB-RUN-005, empirical data now exists for all three tool classes (A, B, C). The cross-class comparison reveals that each class has a **different weakest layer**: Class A = Process (shared extension host), Class B = Identity (no account system), Class C = Network (ephemeral HTTPS). Per-class weight calibration is now empirically justified across the full taxonomy.

---

## 9. Summary

GitHub Copilot (github.copilot-chat v0.37.9 in VS Code 1.109.5) is **readily detectable** through file artifacts and process telemetry, even in an unauthenticated state. The extension leaves a distinctive footprint: 242 files in `~/.vscode/extensions/`, persistent VS Code Application Support data, telemetry logs with device identifiers and Copilot-specific experiment flags, and a clear Electron process tree.

**Key detection anchors (in priority order):**

1. `~/.vscode/extensions/github.copilot-chat-*/` extension directory (File — highest standalone confidence)
2. VS Code process tree with Code Helper (Plugin) extension host (Process — high confidence when cross-correlated with file artifacts)
3. GitHub account authentication state in Keychain + GitHub Authentication log (Identity — highest when authenticated)
4. Persistent HTTPS connections to Microsoft/GitHub infrastructure from Network Service helper (Network — attributable to VS Code PID)
5. VS Code telemetry A/B experiment flags containing `dwcopilot` identifiers (File+Behavior — indicates Copilot presence)

**Key governance challenges (in priority order):**

1. **Personal account on managed endpoint** — the primary evasion concern (Section 12.1). No mechanism to prevent personal GitHub auth without MDM/IdP integration
2. **Extension-host process ambiguity** — process-layer detection cannot distinguish Copilot from other extensions without cross-layer correlation
3. **Agent mode escalation** — VS Code 1.109.5 includes experiment flags for Copilot edit/agent mode, which may escalate from Class A to Class C behavior
4. **Unauthenticated installation** — Copilot can be installed without any authentication, creating a dormant tool presence on managed endpoints

**Playbook validation status:** 4 of 11 IOCs from Section 4.3 confirmed, 2 partially observed, 5 not observed (all due to unauthenticated state, not architectural gaps). 10 new findings to feed back into the playbook. Proposed Class A-specific layer weight calibration with bimodal identity handling.

**Next steps:**
- **CP-POS-02:** Repeat with authenticated GitHub org-managed account — validate identity, behavioral, and network layers
- **CP-EVA-01:** Personal account on managed endpoint — validate the primary evasion scenario
- **CP-POS-03:** Exercise Copilot agent/edit mode — validate Class A→C escalation
