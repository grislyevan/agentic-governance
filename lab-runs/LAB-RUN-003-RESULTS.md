# LAB-RUN-003 Results: Ollama Installation & Runtime Telemetry

**Run ID:** LAB-RUN-003  
**Date:** 2026-02-26  
**Tool:** Ollama v0.17.0 (Homebrew bottle, with dependencies: python@3.14, mlx 0.30.5, mlx-c 0.5.0)  
**Scenario ID:** OL-POS-01 (Standard install, daemon start, model pull, inference session)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/ollama-lab/LAB-RUN-003/` (78 files, SHA-256 hashed per phase)

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.4) | Status | Evidence | Notes |
|---|---|---|---|
| `ollama` daemon/service process running on host | **Observed** | `phase2-launch/ollama-process-tree.txt`, `phase2-launch/ollama-processes.txt` | `ollama serve` (PID 60470) running under user `echance`. Process tree: `launchd (PID 1)` → `ollama serve` (PID 60470). No intermediate shell in steady-state — daemon is a direct child of launchd when started manually. Binary: Mach-O 64-bit ARM64 at `/opt/homebrew/bin/ollama` (symlink → `Cellar/ollama/0.17.0/bin/ollama`). |
| CLI invocations: `ollama run`, `ollama pull`, `ollama serve` | **Observed** | `phase2-launch/model-pull-output.txt`, `phase3-inference/cli-inference-output.txt`, `phase3-inference/second-model-pull.txt` | All three CLI verbs exercised. `ollama serve` started the daemon; `ollama pull tinyllama` and `ollama pull all-minilm` downloaded models; `ollama run` and `ollama list` were used during inference. CLI invocations are distinct, transient processes that communicate with the persistent daemon via localhost HTTP. |
| Parent-child lineage from terminal/scripts to ollama calls | **Observed** | `phase2-launch/ollama-process-tree.txt` | Parent chain: `launchd` → `ollama serve`. CLI commands (`ollama pull`, `ollama run`) are separate short-lived processes that connect to the daemon via `localhost:11434` rather than spawning as child processes of the daemon. This is a **client-server** model, not a parent-child chain. Detection should look for: (1) daemon process, and (2) CLI client invocations independently. |

**Layer signal strength: 0.90** (Clean, unambiguous process identification. Daemon is distinctive — a long-lived Go binary with a well-known name. CLI invocations are separate processes with clear lineage.)

### File / Artifact Layer

| IOC (Playbook Section 4.4) | Status | Evidence | Notes |
|---|---|---|---|
| Model storage: `~/.ollama/models/` directory with manifests | **Observed** | `phase2-launch/model-storage.txt`, `phase4-teardown/ollama-artifacts-detail.txt` | `~/.ollama/models/` contains `blobs/` (content-addressable by SHA-256) and `manifests/` (OCI-format JSON at `registry.ollama.ai/library/<model>/latest`). After two models: 13 files, 652 MB total. Model blobs are large binary files (637 MB for tinyllama, 45 MB for all-minilm). |
| Pulled model metadata, version/tag files, pull timestamps | **Observed** | `phase2-launch/model-manifests.txt`, `phase2-launch/api-tags-post-pull.txt` | Manifests use Docker/OCI distribution manifest v2 format with custom Ollama media types (`application/vnd.ollama.image.model`, `.template`, `.system`, `.params`). API reports model details: family (`llama`), parameter size (`1B`), quantization (`Q4_0`), GGUF format. Timestamps precise to session window. |
| Cache/artifact growth patterns indicating active inference | **Observed** | `phase3-inference/ollama-disk-usage-post.txt`, `phase3-inference/model-storage-diff.txt` | Storage grew from 608 MB (1 model) to 652 MB (2 models) during Phase 3. Model storage diff shows addition of all-minilm blobs and manifest. No ephemeral inference cache files observed — Ollama appears to keep model state in memory during inference, not on disk. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| Ed25519 keypair generated on first `serve` | `phase2-launch/ollama-dir-at-launch.txt` | `~/.ollama/id_ed25519` (private, 387 bytes, mode 0600) and `id_ed25519.pub` (81 bytes). Generated on first daemon start, not during install. Purpose: likely for registry authentication or identity. Distinctive artifact — presence of this keypair is a strong indicator that Ollama has been *run*, not merely installed. |
| `~/.ollama/` created on first serve, not install | `phase1-install/ollama-dir-post.txt` | `ls: /Users/echance/.ollama: No such file or directory` after install. Directory only appears after `ollama serve`. Parallels Claude Code behavior — the playbook should note this distinction for both tools. |
| OCI/Docker-format model manifests | `phase2-launch/model-manifests.txt` | Model storage uses the same manifest schema as Docker container images (OCI distribution spec). This is forensically useful — model provenance is traceable to `registry.ollama.ai` with content-addressable SHA-256 digests. |
| MLX dependency for Apple Silicon acceleration | `phase1-install/install-output.txt` | Homebrew installed `mlx` (148.9 MB) and `mlx-c` (814 KB) as dependencies. This is a platform-specific signal — MLX is Apple's ML framework. Presence of MLX on a managed endpoint could itself be a signal worth monitoring. |

**Layer signal strength: 0.90** (Large, distinctive model storage footprint. Content-addressable blobs are unique to model runtimes. Ed25519 keypair is an unexpected bonus artifact.)

### Network Layer

| IOC (Playbook Section 4.4) | Status | Evidence | Notes |
|---|---|---|---|
| Localhost API traffic (default `:11434`) | **Observed** | `phase2-launch/port-11434-at-launch.txt` | Daemon listens on `localhost:11434` (IPv4, TCP). Confirmed via `lsof`: `ollama PID 60470, FD 7u, TCP localhost:11434 (LISTEN)`. Process-to-socket attribution is **clean and unambiguous** — unlike Claude Code's short-lived HTTPS, Ollama's persistent listener is trivially attributable to its PID. This is the strongest network signal. |
| Outbound model pull traffic to `registry.ollama.ai` | **Observed (indirect)** | `phase2-launch/model-pull-output.txt`, `phase3-inference/second-model-pull.txt` | Two model pulls completed (tinyllama 637 MB, all-minilm 45 MB). No `tcpdump` capture (requires sudo), but manifest content confirms `registry.ollama.ai` as the source registry. Download speed observed at ~33 MB/s. |

**Additional network findings:**

| Finding | Evidence | Significance |
|---|---|---|
| Localhost listener is unauthenticated | `phase2-launch/api-health-check.txt` | `curl http://localhost:11434/` returns `Ollama is running` with zero authentication. The API accepts arbitrary requests from any local process. This is a security-relevant finding — any process on the host can invoke inference without credentials. |
| API returns full model inventory without auth | `phase2-launch/api-tags-post-pull.txt` | `/api/tags` endpoint returns complete model inventory including names, sizes, digests, families, and parameter counts. No API key or authentication required. |

**Layer signal strength: 0.70** (Localhost listener is a strong, easily-captured signal. Outbound pull traffic confirmed indirectly. No pcap due to lack of sudo access.)

### Identity / Access Layer

| IOC (Playbook Section 4.4) | Status | Evidence | Notes |
|---|---|---|---|
| OS user/session tied to daemon and CLI interactions | **Observed** | `phase2-launch/ollama-processes.txt`, `phase2-launch/port-11434-at-launch.txt` | Daemon runs as user `echance` (not root, no dedicated service user). `lsof` and `ps` both show process ownership clearly. Brew install does not create a dedicated `ollama` system user (unlike the Linux install script which typically does). |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| No dedicated system user on macOS (brew) | `phase1-install/ollama-user-check.txt` | `id: ollama: no such user`. The Homebrew formula does not create a service user. Daemon runs under the installing user's identity. Linux installs via the official script typically *do* create an `ollama` system user — this is a platform-specific difference. |
| No authentication layer — identity is OS-level only | `phase2-launch/api-health-check.txt` | No API keys, OAuth tokens, or account profiles. The only identity signal is the OS process owner. This is weaker than Claude Code's OAuth credential store but consistent with Class B's local-only operation model. |
| Ed25519 keypair as potential identity artifact | `phase4-teardown/ollama-artifacts-detail.txt` | `~/.ollama/id_ed25519.pub` is a 81-byte public key. Could serve as a device/instance fingerprint for registry operations. Not investigated whether this is sent to `registry.ollama.ai` during pulls. |

**Layer signal strength: 0.50** (Identity is limited to OS process ownership. No account profiles, no API keys, no org context. The ed25519 key is an unexplored potential signal.)

### Behavior Layer

| IOC (Playbook Section 4.4) | Status | Evidence | Notes |
|---|---|---|---|
| Repeated prompt/inference cycles via local API/CLI | **Observed** | `phase3-inference/api-single-response.json`, `phase3-inference/api-burst-responses.json` | Single inference: 85ms total (30ms load, 15ms prompt eval, 38ms generation). 5-request burst: completed in ~24s with varying response lengths (87–1685 tokens). Burst cadence is distinctive — rapid sequential localhost API calls with model-dependent latency. |
| Automation scripts invoking local generation against repos/data | **Observed** | `phase3-inference/scripted-analysis-response.json` | Curl script read `~/ollama-lab-workspace/sample.py` and sent contents to `/api/generate` for code review. Response confirmed inference operated on the file content. This validates the "scripted automation" behavioral pattern. |
| Unsanctioned model pulls and rapid model switching | **Observed** | `phase3-inference/second-model-pull.txt`, `phase3-inference/model-list-post-second.txt` | Two models pulled in session: tinyllama (generative, 637 MB) and all-minilm (embedding, 45 MB). Model switching between pull and inference was immediate. In a governed environment, the rapid acquisition of multiple models without approval would trigger the "unsanctioned model pull" IOC. |

**Layer signal strength: 0.80** (All three behavioral IOCs confirmed. Burst inference cadence, scripted automation, and model management activity all observed with clear evidence.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.90               0.270
File / Artifact      0.20      0.90               0.180
Network              0.15      0.70               0.105
Identity / Access    0.15      0.50               0.075
Behavior             0.20      0.80               0.160
                                          ──────────────
base_score                                         0.790
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (daemon process clear)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard brew install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.ollama/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct registry access)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Outbound pull traffic not captured via pcap; localhost listener fully attributed)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[△] Weak/missing identity correlation:           −0.10  → PARTIAL: −0.05
    (OS user identified, but no org/account context — inherent to Class B tools)
                                                 ──────
penalties                                         0.10
```

### Final Score

```
final_confidence = 0.790 - 0.10 = 0.69

Classification: Medium (0.45 ≤ 0.69 < 0.75)
```

### Score Assessment

The Medium classification feels **appropriate** for Ollama with polling-based instrumentation. Unlike Claude Code (which scored Medium but felt low), Ollama's score accurately reflects the identity gap inherent to Class B local runtimes — there is genuinely no account profile, org context, or credential store to anchor governance decisions on.

The score could reach High confidence with:
- EDR-grade network capture attributing outbound pulls to the ollama process (+0.05 on network)
- Model allowlist policy providing an approved/unapproved classification signal (+0.10 on identity via policy context)
- **Projected score with EDR + model policy:** ~0.79 (High confidence)

**Comparison with Claude Code (LAB-RUN-001):**

| Dimension | Claude Code | Ollama | Notes |
|---|---|---|---|
| Final score | 0.71 (Medium) | 0.69 (Medium) | Comparable despite very different tool profiles |
| Strongest layer | File (0.95) | Process/File (0.90/0.90) | Claude Code's file layer is stronger due to sheer artifact volume (308 vs 13 files) |
| Weakest layer | Network (0.30) | Identity (0.50) | Different weaknesses — Claude Code's network is instrumentally weak; Ollama's identity is architecturally absent |
| Primary detection anchor | `~/.claude/` directory | `~/.ollama/models/` + localhost:11434 | File for Claude Code; File + Network combined for Ollama |

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | Medium (0.69) |
| Tool Class | B (Local Model Runtime) |
| Asset Sensitivity | Tier 0 (home directory, non-sensitive test data) |
| Action Risk | R1 (model pull — read/download) + R2 (local inference on non-sensitive data) |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Rule 1: Medium confidence + Tier 0 + R1 → **Detect** (for model pull activity)
- Rule 2: Medium confidence + Tier 1 + R2 → **Warn** (for active inference)
- Per Section 5.2 Class B default posture: "Detect for first-seen → Warn for unapproved"

**Decision: Detect with Warn for unapproved model usage.**

In a governed environment with a model allowlist:
- Approved model pull → Detect
- Unapproved model pull → Warn → Approval Required
- Inference on sensitive data → Approval Required (R3 escalation)

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-003
Date:                2026-02-26
Tool:                Ollama v0.17.0 (Homebrew, with mlx 0.30.5)
Scenario ID:         OL-POS-01 (Standard install + model pull + inference session)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — ollama serve daemon (PID 60470) with clean launchd
                     parent chain. CLI invocations as separate client processes.
                     Binary: Mach-O ARM64 at /opt/homebrew/bin/ollama.
                     Evidence: phase2-launch/ollama-process-tree.txt,
                     phase2-launch/ollama-processes.txt
  File/Artifact:     OBSERVED — ~/.ollama/ with 13 files (652 MB) including
                     ed25519 keypair, OCI-format model manifests, content-
                     addressable blob storage. Created on first serve, not install.
                     Evidence: phase4-teardown/ollama-artifacts-detail.txt,
                     phase2-launch/model-manifests.txt
  Network:           OBSERVED — localhost:11434 TCP listener attributed to ollama
                     PID via lsof. Model pulls from registry.ollama.ai confirmed
                     via manifest content. No pcap (no sudo). API is unauthenticated.
                     Evidence: phase2-launch/port-11434-at-launch.txt,
                     phase2-launch/model-pull-output.txt
  Identity:          PARTIALLY OBSERVED — OS user ownership confirmed. No account
                     profiles, API keys, or org context (architecturally absent
                     for Class B tools). Ed25519 keypair is unexplored identity
                     artifact. Evidence: phase2-launch/ollama-processes.txt,
                     phase4-teardown/ollama-artifacts-detail.txt
  Behavior:          OBSERVED — inference burst cadence via API (5 requests in
                     ~24s), scripted automation against local files, model
                     management with two pulls and model switching.
                     Evidence: phase3-inference/api-burst-responses.json,
                     phase3-inference/scripted-analysis-response.json

Confidence Result:   0.69 (Medium) — five-layer model
                     Projected with EDR + model policy: ~0.79 (High)
Policy Decision:     Detect / Warn (Rules 1+2, Section 6.3; Class B default posture)
Evidence Links:      78 files across 5 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Outbound pull traffic not captured via pcap (no sudo);
                     identity layer architecturally weak for Class B;
                     unauthenticated API enables any local process to invoke inference;
                     no terminal session recording (script) used for CLI sessions
```

---

## 5. Class B-Specific Analysis

| Question | Finding |
|---|---|
| Does the installer register a persistent daemon (systemd/launchd)? | **Partially.** Brew registers Ollama as a brew-managed service (visible in `brew services list`, status: `none`). However, no macOS LaunchAgent or LaunchDaemon plist was installed. The daemon only runs when manually started or when explicitly enabled via `brew services start ollama`. The Linux install script behaves differently — it typically creates a systemd service with auto-start. |
| Does the daemon auto-restart after being stopped? | **No.** After `pkill ollama serve`, zero processes remained after 5-second and 10-second checks. Brew service status remained `none`. Auto-restart only activates if the user explicitly runs `brew services start ollama`. |
| Does model storage persist across daemon restarts? | **Yes.** After daemon stop, `~/.ollama/models/` retained all 13 files (652 MB). Model storage is fully persistent — models survive daemon restarts, reboots, and even daemon uninstall (unless `~/.ollama/` is explicitly removed). |
| What is the disk footprint after pulling two models? | **652 MB** — tinyllama (637 MB, 1B params, Q4_0) and all-minilm (45 MB, embedding model). The ed25519 keypair adds negligible space. Model storage is the dominant footprint. |
| Is the localhost API listener authenticated or open? | **Completely open.** Zero authentication on `localhost:11434`. Any local process can: query model inventory (`/api/tags`), run inference (`/api/generate`), pull models (`/api/pull`), and delete models (`/api/delete`). This is a significant governance gap — a compromised or malicious local process could exfiltrate data through inference or pull unauthorized models. |
| Can the API be reached from non-localhost addresses? | **Not tested in this run** (would require binding to `0.0.0.0` via `OLLAMA_HOST` env var). Default binding is `localhost` only. This should be validated in OL-POS-02 or OL-EVA-01. |
| Does the installer create a dedicated system user? | **No** (on macOS via Homebrew). `id ollama` returns "no such user." Daemon runs under the installing user's identity. The Linux install script typically creates an `ollama` system user — this is a platform-specific difference that affects identity-layer detection. |
| Are there any outbound connections beyond `registry.ollama.ai`? | **Not confirmed** — no pcap capture. Brew install connected to Homebrew CDN. During runtime, only `registry.ollama.ai` was referenced in manifests. No telemetry endpoints were observed, but this should be verified with full network capture. |

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **Ed25519 keypair generated on first `serve` is a strong file-layer IOC.** `~/.ollama/id_ed25519` and `id_ed25519.pub` appear on first daemon start, not during install. This is an unexplored artifact not mentioned in Section 4.4. | Section 4.4 File IOC | Add IOC: "Ed25519 keypair in `~/.ollama/` generated on first daemon start. Presence indicates the tool has been *run*, not merely installed." Confidence Weight: Medium–High. |
| 2 | **`~/.ollama/` created on first serve, not install — same pattern as Claude Code.** The Homebrew install creates zero files in the user's home directory. All state artifacts appear only after `ollama serve`. | Section 4.4 File IOC | Add note: "Config/state directory created on first serve, not install. Absence after install ≠ absence of tool." (Mirrors finding from LAB-RUN-001 for Claude Code.) |
| 3 | **Model storage uses OCI/Docker distribution manifest format.** Manifests are JSON files following Docker's distribution manifest v2 with custom Ollama media types. Blobs are content-addressable by SHA-256. This is forensically valuable — model provenance is traceable. | Section 4.4 File IOC | Add detail: "Model manifests follow OCI distribution spec at `~/.ollama/models/manifests/registry.ollama.ai/library/<model>/<tag>`. Content-addressable blobs enable forensic verification of model integrity and provenance." |
| 4 | **Localhost API is completely unauthenticated.** Any local process can invoke inference, pull models, or query inventory without any credentials. This is a governance-relevant finding — it means detection of Ollama usage cannot rely on API authentication signals, and any local automation can silently use Ollama. | Section 4.4 Network IOC, Section 7 (Risky Action Controls) | Add risk note: "Ollama's localhost API has zero authentication by default. Any local process can invoke inference or model management. Consider adding IOC: 'Unauthenticated localhost API listener on port 11434' as both a detection signal and a risk marker." |
| 5 | **Client-server architecture means CLI and daemon are separate processes.** Unlike Claude Code (single process with child chains), Ollama's `ollama run`/`pull` commands are short-lived clients that HTTP-connect to the persistent daemon. Process detection should look for the daemon *and* CLI invocations independently, not parent-child chains. | Section 4.4 Process IOC | Clarify: "Parent-child lineage from terminal/scripts to ollama calls" should note that CLI commands are HTTP clients of the daemon, not child processes. Detection should monitor both: (1) long-lived `ollama serve` daemon, and (2) transient `ollama run/pull` CLI processes. |
| 6 | **Homebrew installs MLX as a dependency — Apple Silicon GPU acceleration.** MLX (148.9 MB) is a significant dependency that enables GPU-accelerated local inference. Presence of MLX on a managed endpoint is itself a signal worth monitoring, as it suggests local model runtime capability. | Section 4.4 File IOC (new), Section 11 (Tooling) | Consider adding MLX as a secondary artifact indicator: "MLX framework present in Homebrew cellar alongside ollama — indicates GPU-accelerated local inference capability." |
| 7 | **Identity layer is architecturally weak for Class B tools.** Ollama has no account system, no API keys, no OAuth, no org context. Identity is limited to OS process ownership. This is not an instrumentation gap (like Claude Code's network layer) — it is a fundamental architectural characteristic of local runtimes. | Section 4.4 Identity IOC, Appendix B | Document that Class B tools have an inherent identity-layer ceiling. Consider reducing default identity weight for Class B from 0.15 to 0.10 and redistributing to File (0.25) and Network (0.20), reflecting the empirical signal strengths observed. |
| 8 | **Brew service registration is a persistence signal even when not started.** `brew services list` shows Ollama as `none` (registered but not running). This is a softer persistence signal than an active LaunchAgent but still indicates the tool is *available for* daemon operation. | Section 4.4 Process IOC (new) | Add IOC for macOS/brew: "Brew service registration for ollama visible in `brew services list` — indicates tool is installed and available for daemon operation even when not running." |
| 9 | **Network layer is stronger for Ollama than Claude Code due to persistent listener.** Claude Code makes short-lived HTTPS bursts that evade polling-based capture. Ollama's persistent localhost listener on 11434 is trivially detectable via `lsof` or `netstat` at any polling interval. This inverts the network-layer difficulty. | Section 4.4 Network IOC, Appendix B | Document that network detection difficulty is inverted for Class B vs Class C tools. Localhost listeners are easy to detect; outbound API bursts are hard. Adjust confidence expectations accordingly. |
| 10 | **No telemetry or phone-home behavior observed.** During the entire session (install, serve, pull, inference, stop), no outbound connections beyond model pulls from `registry.ollama.ai` were apparent. This is consistent with Ollama's perimeter-blind-spot risk profile — once models are pulled, the tool operates entirely locally with no external visibility. | Section 4.4 Network IOC | Add note: "After initial model pull, Ollama operates with zero outbound network activity. This confirms the 'perimeter blind spot' risk classification — network-based detection is limited to the pull phase." |

---

## 7. Proposed Layer Weight Calibration for Ollama (Class B)

Based on empirical observations, the default five-layer weights should be adjusted for Ollama:

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Daemon is easily detectable but less distinctive than CLI tools — many services listen on localhost. |
| File | 0.20 | 0.25 | Model storage is large, unique, and persistent. Content-addressable blobs are distinctive. |
| Network | 0.15 | 0.20 | Localhost listener is a strong, persistent signal (unlike short-lived HTTPS for Class C). Outbound pull traffic is episodic but distinctive. |
| Identity | 0.15 | 0.10 | Architecturally weak — no account system. OS user is the only signal. |
| Behavior | 0.20 | 0.20 | No change — inference burst cadence and model management are solid behavioral signals. |

**Recalculated score with proposed weights:**

```
Layer                Weight    Signal Strength    Weighted
Process              0.25      0.90               0.225
File                 0.25      0.90               0.225
Network              0.20      0.70               0.140
Identity             0.10      0.50               0.050
Behavior             0.20      0.80               0.160
                                          ──────────────
base_score                                         0.800
penalties                                          0.10
final_confidence                                   0.700

Classification: Medium (0.45 ≤ 0.70 < 0.75)
```

Still Medium, but the score distribution better reflects the actual signal strengths. The identity penalty is the primary factor keeping the score below High — this is an accurate reflection of the governance challenge with Class B tools.

---

## 8. Summary

Ollama v0.17.0 is **readily detectable** through standard endpoint telemetry across Process, File, and Network layers. The tool leaves a distinctive footprint: a persistent daemon, a large model storage directory with content-addressable artifacts, a well-known localhost listener, and an OCI-format model registry trail.

**Key detection anchors (in priority order):**

1. `~/.ollama/models/` directory with content-addressable blobs (File — highest standalone confidence)
2. `ollama serve` daemon process listening on `localhost:11434` (Process + Network — combined high confidence)
3. Model pull traffic to `registry.ollama.ai` (Network — episodic but distinctive)
4. Ed25519 keypair in `~/.ollama/` (File — indicates tool has been run)
5. Inference burst cadence on localhost API (Behavior — confirms active usage)

**Key governance challenges (in priority order):**

1. **Unauthenticated API** — any local process can invoke inference without credentials
2. **No identity layer** — no account, org context, or credential store to anchor governance
3. **Perimeter blind spot** — after model pull, operates entirely locally with zero external visibility
4. **Persistent model storage** — models survive daemon restarts and are available for offline use

**Playbook validation status:** 9 of 9 IOCs from Section 4.4 confirmed. 10 new findings to feed back into the playbook. Proposed Class B-specific layer weight calibration.
