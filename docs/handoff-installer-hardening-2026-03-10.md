# Handoff: Windows Installer Hardening & Agent Download Fix

**Date:** 2026-03-10
**Scope:** Windows Server installer (`DetecServerSetup.exe`), build pipeline, agent download endpoint
**Commits:** `1ffd672`, `6de1ec8`, `894e21b` (all pushed to `origin/main`)
**Deployed to:** Windows Server VM at `192.168.64.4`

---

## What Was Done

### 1. Security: Credential Passing (Critical)

**Problem:** The admin password was passed as a CLI argument to `detec-server.exe setup --admin-password "..."`. On Windows, any user can see process command lines via Task Manager or `wmic process list`.

**Fix:**
- `server_cli.py` now reads `DETEC_ADMIN_PASSWORD` from the environment as a fallback before auto-generating.
- The Inno Setup script uses `SetEnvironmentVariableW` (imported from `kernel32.dll`) to set the password in the installer process's environment block before launching the child process, then clears it immediately after.
- The password never appears in any process listing.

**Files:** `api/server_cli.py`, `packaging/windows/installer/detec-server-setup.iss`

### 2. Upgrade Safety: Stop Service Before File Extraction

**Problem:** When upgrading over an existing installation, Inno Setup tried to overwrite binaries while the service was running, causing locked-file errors on Windows.

**Fix:** Added `PrepareToInstall` function in the Inno Setup `[Code]` section. It queries `sc.exe` for the `DetecServer` service and stops it (with a 2-second wait) before file extraction begins.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 3. Error Handling: Early Exit on Setup Failure

**Problem:** All 5 post-install steps ran unconditionally. If step 2 (config generation) failed, steps 3-5 would still run and the Finish page would show no clear error.

**Fix:**
- Added `InstallHadErrors` tracking flag.
- Step 2 failure now halts post-install immediately with manual recovery instructions.
- Steps 3-5 failures are tracked and surfaced in the install log.
- The Finish page displays a warning when errors occurred.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 4. Port Check: Replaced Netstat with Get-NetTCPConnection

**Problem:** The `netstat -an | findstr` approach could false-match on port substrings (e.g., port 80001 matching a check for port 8000).

**Fix:** Replaced with a PowerShell `Get-NetTCPConnection -LocalPort X -State Listen` check, which matches exact ports.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 5. Gateway Firewall Rule

**Problem:** The installer only opened the API port in the firewall. The binary protocol gateway (port 8001) was missing, while `deploy.ps1` opened both.

**Fix:** The installer now creates a "Detec Gateway" firewall rule for TCP 8001. The uninstaller cleans it up.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 6. Agent Download: Packages Bundled into Installer

**Problem:** The dashboard's "Download Agent" button returned a 404 because `dist/packages/` was empty. The build pipeline never built or bundled the agent.

**Fix:**
- `build-installer.ps1` expanded from 5 steps to 7. New step 4 builds `detec-agent.exe` via PyInstaller, zips the output directory, and places `detec-agent.zip` in `dist/detec-server/dist/packages/`.
- Inno Setup's recursive file copy (`recursesubdirs`) picks it up automatically.
- The script also checks for a macOS `.pkg` at `dist/DetecAgent-latest.pkg` and includes it if found.
- `agent_download.py` now uses `sys.executable` in frozen (PyInstaller) mode to resolve the packages directory, rather than relying on `__file__` traversal.
- Old installer artifacts are deleted before Inno Setup compiles, so stale `.exe` files can't mask compile failures.

**Files:** `packaging/windows/build-installer.ps1`, `api/routers/agent_download.py`

### 7. CI Fix: Missing `[dev]` Extras

**Problem:** CI ran `pip install -e ".[dev]"` but the `dev` optional-dependencies group didn't exist in `pyproject.toml`, so pytest was missing. The fallback `|| pip install -e .` silently swallowed the error.

**Fix:** Added the `dev` group with `pytest>=7.0.0` and `pytest-cov>=4.0.0`. Removed the silent fallback in `ci.yml`.

**Files:** `pyproject.toml`, `.github/workflows/ci.yml`

---

## Deployment Summary

Rebuilt and redeployed on Windows Server VM (`192.168.64.4`):

| Step | Result |
|------|--------|
| `git pull` | Fast-forward to `894e21b`, 9 files updated |
| `build-installer.ps1` | 7/7 steps passed. Server: 10.2 MB, Agent: 3.6 MB, Agent zip: 13.2 MB, Installer: 35.6 MB |
| Service install + start | Running, DB freshly seeded |
| Agent download (Windows) | 200 OK, 13.7 MB zip with `detec-agent.zip`, `agent.env`, `collector.json`, `README.md` |
| Agent download (macOS) | Expected 404 (no .pkg available on Windows build machine) |

**Current credentials:** `admin@example.com` / `D3tec-Adm1n-2026!` (change these).

---

## Installer Polish (follow-up pass)

Brand-aligned UX improvements applied to the wizard after the hardening pass above.

### 8. Post-install Health Check

**Problem:** The installer declared success based on `sc start` returning 0, but the service could crash moments later. No confirmation that the dashboard was actually reachable.

**Fix:** Added step `[6/6] Verifying dashboard is responding...` after the firewall step. Polls `http://localhost:{port}/docs` via PowerShell `Invoke-WebRequest` up to 15 times (1 s apart). On success: logs "done". On timeout: logs a WARNING and sets `InstallHadErrors` so the Finish page reflects the issue.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 9. Install Log Persistence

**Problem:** The `LogMemo` text vanished when the user clicked Finish. Support had no breadcrumb trail for early failures.

**Fix:** At the end of post-install, the installer writes the full log to `C:\ProgramData\Detec\install.log` via `SaveStringsToFile`. A final line confirms the path.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 10. Wizard Copy Polish

Updated wizard page subtitles and validation messages to align with the Detec brand voice ("precise but human", "helpful, non-blaming"):

- Page subtitles: warmer, conversational tone (e.g. "One last look before we get started.")
- Validation errors: rewritten to explain the issue without blaming (e.g. "That email looks incomplete. Make sure it includes an @.")
- Pre-flight summary: "All clear. Ready when you are." / "A few things need attention before we continue."

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 11. Finish Page Guidance and Duplicate-Button Fix

**Problem:** The Finish page had only a bare "Open Detec Dashboard" button. Navigating Back then Forward created duplicate buttons.

**Fix:**
- Added `FinishPageCreated` flag to gate control creation (prevents duplicates).
- Added a `TNewStaticText` label above the button with context-aware summary text: running port, admin email, and a next-step prompt ("deploy agents from Settings > Download Agent"). On error, the label switches to a warning directing the admin to `server.log`.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 12. Shift-Click Easter Egg

Holding Shift while clicking "Open Detec Dashboard" on the Finish page opens `C:\ProgramData\Detec\server.log` in Notepad instead of the browser. Imported `GetKeyState` from `user32.dll` to detect the modifier.

**File:** `packaging/windows/installer/detec-server-setup.iss`

### 13. Wizard Artwork Enhancement

**Problem:** `generate-assets.py` used a fragile font fallback chain (only `arial.ttf` and macOS Helvetica) and the sidebar image had no descriptor text.

**Fix:**
- Added the brand descriptor tagline ("Endpoint governance for agentic AI") below the "Detec" text in a smaller, muted-gray font.
- Introduced `_load_font()` helper with a six-path fallback chain: bundled font in `branding/fonts/`, `arial.ttf`, `segoeui.ttf`, Helvetica, DejaVu Sans, then Pillow default. This resolves the headless Server Core issue.
- Added `FONTS_DIR` constant; the script prints a note if the directory is absent (graceful, not fatal).

**File:** `packaging/windows/installer/generate-assets.py`

---

## Remaining Recommendations

| Item | Priority | Description |
|------|----------|-------------|
| PostgreSQL connection validation | High | When user selects PostgreSQL, test connectivity before leaving the Config page. |
| Privileged port warning | Medium | Warn (don't block) for ports below 1024 or well-known ports. |
| Pin Inno Setup version | Medium | `build-installer.ps1` finds any Inno Setup 6 but doesn't verify exact version. |
| Build pipeline error surfacing | Medium | Steps 1-2 pipe stderr to `Out-Null`; partial pip failures produce broken bundles silently. |
| Version coupling | Medium | `AppVersion` is hardcoded as `0.1.0` in the `.iss` file while `pyproject.toml` says `0.3.0`. Source from one place. |
| Shortcut via `[Icons]` section | Low | Use Inno Setup's built-in `[Icons]` instead of COM `WScript.Shell` for the desktop shortcut. |

---

## File Change Summary

### Hardening pass (commits `1ffd672`, `6de1ec8`, `894e21b`)

9 files changed, 223 insertions, 43 deletions:

| File | What Changed |
|------|-------------|
| `api/server_cli.py` | `DETEC_ADMIN_PASSWORD` env var fallback in `cmd_setup` |
| `api/routers/agent_download.py` | `sys.executable`-based frozen path resolution for `_DIST_DIR` |
| `packaging/windows/installer/detec-server-setup.iss` | Win32 API import, env-based password passing, `PrepareToInstall` service stop, error tracking, PowerShell port check, gateway firewall rule |
| `packaging/windows/build-installer.ps1` | 5-step to 7-step pipeline (agent build + zip), stale artifact cleanup, collector package install, macOS .pkg detection |
| `packaging/windows/README.md` | Updated wizard description, security notes, upgrade behavior, agent bundling |
| `SERVER.md` | GUI installer as primary Option B, agent download setup instructions |
| `PROGRESS.md` | 3 new M2 line items |
| `pyproject.toml` | `[dev]` optional-dependencies group |
| `.github/workflows/ci.yml` | Removed silent fallback on `pip install -e ".[dev]"` |

### Polish pass (items 8-13)

2 files changed:

| File | What Changed |
|------|-------------|
| `packaging/windows/installer/detec-server-setup.iss` | `GetKeyState` import, `FinishPageCreated` flag, brand-voice copy on subtitles and validation, 6-step post-install (added health check), install log persistence, Finish page guidance text with duplicate-button fix, Shift-click easter egg |
| `packaging/windows/installer/generate-assets.py` | `_load_font()` fallback chain, `FONTS_DIR` constant, tagline text on sidebar image, `SLATE_400` color for muted text |

---

## macOS Agent Downloads

The macOS `.pkg` can only be built on macOS. To enable macOS downloads from the Windows-hosted server:

1. On a Mac: `bash packaging/macos/build-pkg.sh`
2. Copy `dist/DetecAgent-*.pkg` to the Windows build machine at `dist/DetecAgent-latest.pkg`
3. Re-run `build-installer.ps1` (the script detects and includes it automatically)
4. Reinstall the server with the new installer
