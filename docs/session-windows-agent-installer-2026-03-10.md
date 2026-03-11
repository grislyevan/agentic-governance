# Session: Windows Agent Installer EXE (2026-03-10)

## Objective

Replace the manual zip-extract-and-run Windows agent deployment with a proper Inno Setup installer. The target UX: admin clicks "Download Installer" in the dashboard, an EXE downloads, user double-clicks it, installer shows progress, and the agent appears in the system tray connected to the server.

## What Was Done

### 1. Agent Inno Setup installer (`detec-agent-setup.iss`)

Created `packaging/windows/installer/detec-agent-setup.iss`, an Inno Setup script that produces `DetecAgentSetup-0.3.0.exe`.

Wizard flow: Welcome > License > Installing (progress log) > Finish

The installer bundles both `detec-agent.exe` (headless Windows Service) and `detec-agent-gui.exe` (system tray app with status window). Post-install steps:

1. Extract embedded config (API URL, key, interval) from the installer EXE via PowerShell
2. Write `agent.env` + `collector.json` to `C:\ProgramData\Detec\Agent\`
3. Register the `DetecAgent` Windows Service
4. Start the service
5. Launch the tray app as the original (non-elevated) user
6. Register the tray app for auto-start via `HKCU\...\Run` registry key

Uninstall stops the service, removes it, kills the GUI, deletes the registry key, and offers to remove the data directory.

### 2. Zero-touch config embedding

The pre-built installer EXE is a vanilla Inno Setup binary. At download time, the API server appends tenant configuration to the end of the EXE:

```
[original EXE bytes] [DETEC_CFG_V1\0] [JSON config] [4-byte LE length] [DETEC_CFG_V1\0]
```

The installer's post-install step writes a PowerShell script to `{tmp}`, executes it, and the script reads the setup EXE's own bytes from the end to find and extract the config JSON. If no magic marker is found (generic build), the step is silently skipped.

### 3. Updated build pipeline (`build-installer.ps1`)

Expanded the build pipeline from 7 steps to 9:

| Step | Description |
|------|-------------|
| 1 | Python dependencies (added `pystray` to pip install) |
| 2 | Dashboard build |
| 3 | PyInstaller: `detec-server.exe` |
| 4 | PyInstaller: `detec-agent.exe` (headless) |
| 5 | **NEW**: PyInstaller: `detec-agent-gui.exe` (tray app) |
| 6 | Branding assets |
| 7 | **NEW**: Inno Setup: `DetecAgentSetup.exe` (agent installer) |
| 8 | Bundle agent packages + Inno Setup: `DetecServerSetup.exe` |
| 9 | Summary |

The agent installer EXE is copied into `dist/detec-server/dist/packages/` so it ships inside the server installer and is available for dashboard downloads. The existing `detec-agent.zip` is still created alongside it for scripted/MDM deployments.

### 4. API download endpoint (`agent_download.py`)

- `_PLATFORM_PACKAGES["windows"]` now prefers `DetecAgentSetup.exe`, falling back to `detec-agent.zip`
- Added `_embed_config_in_exe()`: appends magic-marker-delimited JSON config to EXE bytes
- Added `_build_download_response()`: dispatches between EXE (direct serve with embedded config) and zip (existing behavior) based on file extension
- Both download endpoints (`GET /agent/download` and `GET /agent/download/{token}`) use the new dispatcher
- Updated Windows README template for the zip fallback case

### 5. Dashboard (`SettingsPage.jsx`)

Download button text is now context-aware: shows "Download Installer" when Windows is selected, "Download Agent" for macOS/Linux.

## Files Changed

| File | Change |
|------|--------|
| `packaging/windows/installer/detec-agent-setup.iss` | **NEW**: Agent Inno Setup installer script |
| `packaging/windows/build-installer.ps1` | Added GUI agent build (step 5), agent ISS compilation (step 7), updated step numbering |
| `api/routers/agent_download.py` | EXE preference for Windows, config embedding, response dispatcher |
| `dashboard/src/pages/SettingsPage.jsx` | "Download Installer" label for Windows |

## Architecture

```
Dashboard "Download Installer" (Windows)
  |
  v
GET /api/agent/download?platform=windows
  |
  v
API reads dist/packages/DetecAgentSetup.exe
  |
  v
Appends: [DETEC_CFG_V1\0] [JSON] [4-byte len] [DETEC_CFG_V1\0]
  |
  v
Serves modified EXE (application/octet-stream)
  |
  v
User double-clicks DetecAgentSetup.exe
  |
  v
Inno Setup wizard: Welcome > License > Progress > Finish
  |
  v
Post-install: PowerShell extracts config from EXE tail
  |
  v
Service installed + started, tray icon launched, auto-start registered
```

## Build Prerequisites

To build the agent installer on a Windows machine:

- Python 3.11+ with `pyinstaller`, `pywin32`, `pystray`, `Pillow`
- Inno Setup 6 (`iscc.exe` on PATH or default install location)
- Run: `powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1`

## Known Considerations

- **Code signing**: The config-appended EXE will not carry a digital signature. If code signing is added later, the signing must happen before config embedding, and the Authenticode signature will be invalidated by the append. An alternative would be to use a dual-signature approach or embed config via a different mechanism (e.g., overlay data that Authenticode excludes).
- **Antivirus**: Some AV heuristics flag modified EXEs. In testing, major AV products accept Inno Setup installers with appended data, but this should be monitored.
- **Fallback**: If `DetecAgentSetup.exe` is not present in `dist/packages/`, the API falls back to `detec-agent.zip` with the original zip-based flow.
