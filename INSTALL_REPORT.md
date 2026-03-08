# Detec Agent: Install and Monitor Report

**Date:** 2026-03-08
**Machine:** echance-mbp (Darwin 25.3.0 arm64, macOS Sequoia)
**Agent version:** 0.3.0 (event schema 0.4.0)
**Python:** 3.11.6 (pyenv)

---

## 1. Installation

```bash
pip install -e .
```

All dependencies were already satisfied (`jsonschema`, `watchdog`, `psutil`, `cryptography`). The editable install completed without errors.

**Verification:**

| Check | Result |
|---|---|
| `which detec-agent` | `/Users/echance/.pyenv/shims/detec-agent` |
| `detec-agent --help` | Displayed full usage (12 options). Exit 0. |

---

## 2. What Was Run

**Mode:** One-shot dry-run (no API needed).

```bash
detec-agent --dry-run --verbose
```

The scan took approximately 29 seconds, examined 11 scanner profiles, and completed with **exit code 0**.

**Summary line:**

```
Scan complete. Events emitted: 18, validation failures: 0
```

No API URL or key was configured. Daemon mode was not started because there is no live API endpoint available. The `--dry-run` flag printed all events to stdout instead of writing to a file.

---

## 3. Detections

The agent detected 9 tools on this endpoint. Key findings:

| Tool | Class | Confidence | Policy | Severity | Notes |
|---|---|---|---|---|---|
| **OpenClaw** | D | 0.855 (High) | block | S3 | Autonomous daemon, self-authored skills, embedded creds in plist, cron jobs. Strongest detection. |
| **Cursor** | A | 0.645 (Medium) | warn | S1 | 51 processes, 2059 files, ai-code-tracking.db, 50 agent transcripts, sandbox active. |
| **Claude Code** | C | 0.315 (Low) | detect | S0 | CLI processes (PIDs 1714/1715), ~/.claude/ with 40 files, version 2.1.59. |
| **GitHub Copilot** | A | 0.253 (Low) | detect | S0 | Extension installed (0.37.9) but not authenticated (dormant). |
| **Open Interpreter** | C | 0.160 (Low) | detect | S0 | Likely false positive; matched generic `interpreter` process names (ps, ls, find). |
| **Continue** | A | 0.158 (Low) | detect | S0 | Matched Cursor extension host processes + OPENAI_API_KEY in env. |
| **Cline** | A | 0.158 (Low) | detect | S0 | Same as Continue; extension host process + API key signal. |
| **GPT-Pilot** | B | 0.055 (Low) | detect | S0 | Only signal: OPENAI_API_KEY in env. No process, no files. |
| **Aider** | C | 0.055 (Low) | detect | S0 | Only signal: OPENAI_API_KEY in env. Not installed. |

All 18 events (9 detection.observed + 9 policy.evaluated) passed JSON Schema validation.

---

## 4. macOS Security and Permissions

### 4.1 Permission Errors Observed

| Issue | Where | Impact |
|---|---|---|
| `net_connections: access denied (needs elevation)` | Ollama network scan, Cursor network scan | `psutil.net_connections()` requires root on macOS. The agent gracefully degrades: network signals score 0 for tools that rely on connection enumeration. No crash. |

This is the **only** permission issue encountered. The agent's `compat.network` module catches the `AccessDenied` exception and logs it at DEBUG level.

### 4.2 What Did NOT Trigger Errors

- **Process listing:** `psutil.process_iter()` worked without elevation. All process scans succeeded.
- **File access:** Reading `~/Library`, `~/.cursor`, `~/.claude`, `~/.openclaw`, `/Applications` all succeeded with no permission errors.
- **macOS dialogs:** No Full Disk Access, Accessibility, or other TCC prompts appeared during the scan.
- **Keychain:** Not accessed (no `--api-key` needed for dry-run). If daemon mode were configured, the agent would call `security find-generic-password` for the `detec-agent` service. That command may prompt for Keychain access on first use, depending on Keychain settings.
- **Sandbox errors:** No "Operation not permitted" or sandbox-style failures.

### 4.3 Non-Permission Warnings (Expected)

Commands like `ollama --version`, `open-interpreter --version`, and `aider --version` returned `ENOENT` ("No such file or directory") because those tools are not installed. This is normal and the scanner treats it as "version unknown."

### 4.4 Recommendation for Full Network Visibility

To get network-layer signals (which would raise confidence for tools like Claude Code), the agent would need to run with `sudo` or be granted the relevant entitlement. In practice, this is a minor gap: file and process signals already provide strong attribution for most tools.

---

## 5. LaunchAgent (Not Installed)

The LaunchAgent plist is ready at `deploy/macos/com.detec.agent.plist`. It was not loaded because no live API endpoint is available. To install:

```bash
cp deploy/macos/com.detec.agent.plist ~/Library/LaunchAgents/
# Edit the plist: replace https://api.example.com with your real API URL
launchctl setenv AGENTIC_GOV_API_KEY "your-api-key"
launchctl load ~/Library/LaunchAgents/com.detec.agent.plist
```

Logs would go to `/tmp/detec-agent.log` and `/tmp/detec-agent.err`.

Alternatively, store the API key in Keychain (the agent reads it automatically):

```bash
security add-generic-password -s detec-agent -a api-key -w "your-api-key"
```

---

## 6. References

- `DEPLOY.md` — install, config, auto-start, Keychain/Credential Manager
- `deploy/macos/com.detec.agent.plist` — LaunchAgent template
- `collector/agent/credentials.py` — Keychain usage (service `detec-agent`, account `api-key`)
- `collector/main.py` — CLI entrypoint and daemon loop
