# Windows Packaging

Build and install Detec components as Windows Services.

## GUI Installers (recommended for clients)

Both installers use a full dark theme (Slate 900 background, Soft Indigo accent bar, Segoe UI header typography) built with [Inno Setup 6](https://jrsoftware.org/isdl.php). They support `/VERYSILENT` for fully headless deployment.

### Building

On your build machine (requires Python 3.11+, Node.js 22+, and Inno Setup 6):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
```

This runs the full pipeline: dashboard build, server PyInstaller bundle, agent PyInstaller bundle + zip, branding asset generation, and Inno Setup compilation. Output: `packaging/windows/dist/DetecServerSetup-0.1.0.exe` and `DetecAgentSetup-0.3.0.exe`.

The server installer bundles the Windows agent package (`detec-agent.zip`) inside `dist/packages/` so agent downloads work from the dashboard immediately after install. To also include macOS agent downloads, build the .pkg on a Mac (`bash packaging/macos/build-pkg.sh`) and place it at `dist/DetecAgent-latest.pkg` or `dist/DetecAgent.pkg` before running `build-installer.ps1`.

### Server installer (`DetecServerSetup.exe`)

The wizard walks the user through these steps:

1. **Welcome**
2. **License agreement**: accept the Detec Server EULA
3. **Pre-flight checks**: validates disk space (300 MB minimum), port availability (via `Get-NetTCPConnection`), detects existing installations or services
4. **Server configuration**: choose the API port (default 8000) and database backend (SQLite or PostgreSQL with connection URL)
5. **Administrator account**: enter the admin email, password, and confirmation (validated for format and minimum length)
6. **Installation summary**: review all chosen settings before proceeding
7. **File extraction + post-install**: extracts the server bundle to `C:\Program Files\Detec\Server\`, generates secrets and the administrator account, installs and starts the Windows Service, configures firewall rules for both the API port and gateway port (8001), creates a desktop shortcut, and verifies the dashboard is responding (polls for up to 15 seconds)
8. **Finish page**: shows a context-aware summary (running port, admin email, next-step guidance) and an "Open Detec Dashboard" button. Hold Shift while clicking the button to open the server log in Notepad instead.

### Agent installer (`DetecAgentSetup.exe`)

No wizard pages. The installer shows only a branded progress log during install, then auto-closes with a brief countdown. When downloaded from the Detec Server dashboard, the installer has tenant configuration (API URL, key, interval) embedded and applies it automatically (zero-touch). If no embedded config is found, the agent installs but requires manual setup via `detec-agent setup`.

#### Service registration

Post-install runs the agent binary from the install directory with working directory set to the app directory so the Windows Service is registered with the correct paths:

- **Binary path:** `{app}\detec-agent.exe` (e.g. `C:\Program Files\Detec\Agent\detec-agent.exe`).
- **Working directory:** `{app}`. The Inno Setup `[Code]` section calls `Exec(Filename, Params, WorkDir, ...)` with `WorkDir = AppDir` for both `install` and `start`.
- **Steps:** `detec-agent.exe install`, then `detec-agent.exe start`, then `detec-agent.exe set-recovery` (configures restart-on-failure).

The service is therefore created with the correct image path and can load config from `%PROGRAMDATA%\Detec\Agent\` at runtime.

#### Security

- Admin credentials are passed to the setup process via environment variable, not on the command line, to prevent exposure in Task Manager or process listings.
- If the setup step (config generation) fails, post-install halts early and displays manual recovery instructions.

#### Install log

The installer writes a log of all post-install steps to `C:\ProgramData\Detec\install.log`. This persists after the wizard closes, so support can diagnose failures after the fact.

#### Upgrades

When an existing Detec Server service is detected, the installer stops it before extracting files to avoid locked-file errors. The service is reinstalled and restarted after extraction.

#### Uninstaller

Registered in Add/Remove Programs. It stops and removes the Windows Service, deletes both firewall rules (API and gateway), removes installed files, and optionally removes the data directory (`C:\ProgramData\Detec\`).

---

## One-Command Deploy (Fresh VM)

On a brand-new Windows Server with nothing installed, open an elevated PowerShell and run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process
irm https://raw.githubusercontent.com/grislyevan/agentic-governance/main/packaging/windows/bootstrap.ps1 | iex
```

This installs Python 3.11, Node.js 22 LTS, and Git silently, clones the repo, builds both executables, runs setup, installs the server as a Windows Service, opens the firewall, and places a "Detec Dashboard" shortcut on the desktop. Total hands-off time: roughly 5-10 minutes depending on download speed.

If you already have the prerequisites installed, run the deploy script directly:

```powershell
Set-ExecutionPolicy Bypass -Scope Process
cd C:\Detec\src\packaging\windows
.\deploy.ps1
```

## Manual Build (Server)

From an elevated PowerShell prompt:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build.ps1
```

This produces `packaging/windows/dist/detec-server/` containing `detec-server.exe` and all dependencies.

## Manual Build Steps

```powershell
# 1. Install dependencies
pip install -r api/requirements.txt
pip install pyinstaller pywin32

# 2. Build the dashboard
cd dashboard
npm install && npm run build
cd ..

# 3. Run PyInstaller
cd packaging/windows
pyinstaller --clean --noconfirm detec-server.spec
```

## Usage

### First-run setup

```powershell
cd dist\detec-server
.\detec-server.exe setup --admin-email admin@yourorg.com
.\detec-server.exe setup --admin-email admin@yourorg.com --port 9000
.\detec-server.exe setup --admin-email admin@yourorg.com --database-url "postgresql://user:pass@host:5432/detec"
```

This generates a `server.env` in `C:\ProgramData\Detec\` with a random JWT secret and seed admin password. The `--port` flag sets the API port (default 8000). The `--database-url` flag overrides the default SQLite database with a PostgreSQL connection string. Save the password shown on screen.

### Run in foreground (testing)

```powershell
.\detec-server.exe run
```

Open http://localhost:8000 in a browser.

### Install as a Windows Service

From an elevated (Administrator) command prompt:

```powershell
.\detec-server.exe install
.\detec-server.exe start
```

The service runs as "Detec Server", starts automatically on boot, and survives logoff/reboot. A "Detec Dashboard" shortcut is placed on the Public Desktop during deployment. The server is accessible at http://localhost:8000.

### Manage the service

```powershell
.\detec-server.exe stop      # stop the service
.\detec-server.exe start     # start the service
.\detec-server.exe remove    # unregister the service
.\detec-server.exe status    # show config and service status
```

### Data locations

| Item | Path |
|------|------|
| Database | `C:\ProgramData\Detec\detec.db` |
| Config | `C:\ProgramData\Detec\server.env` |
| Server log | `C:\ProgramData\Detec\server.log` (stdout/stderr when running as a service) |
| Install log | `C:\ProgramData\Detec\install.log` (written by the GUI installer) |
| Event log | Windows Event Log (Application, source "DetecServer") |

### Backup

Copy `C:\ProgramData\Detec\detec.db` while the service is running (SQLite WAL mode supports hot copies). For a consistent snapshot, stop the service first.

### Firewall

If agents connect from other machines, allow inbound TCP on the server ports:

```powershell
New-NetFirewallRule -DisplayName "Detec Server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
New-NetFirewallRule -DisplayName "Detec Gateway" -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow
```

Port 8001 is only needed when agents use `--protocol tcp` (binary wire protocol).

---

## Detec Agent (Collector)

### Quick Build (headless service)

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build-agent.ps1
```

This produces `packaging/windows/dist/detec-agent/` containing `detec-agent.exe`.

### Build GUI tray app

```powershell
pip install pystray Pillow
cd packaging\windows
pyinstaller --clean --noconfirm detec-agent-gui.spec
```

This produces `packaging/windows/dist/detec-agent-gui/` containing `detec-agent-gui.exe`. The GUI provides a system tray icon and status window. Double-click to launch; right-click the tray icon for scan controls and quit.

### One-shot scan (testing)

```powershell
cd dist\detec-agent
.\detec-agent.exe scan --verbose
```

### Configure the agent

**Option A: Download pre-configured from the dashboard** (zero-touch). In the Detec dashboard, go to Settings, select Windows, and click "Download Agent". The resulting zip contains the agent plus a `collector.json` with the server URL and tenant agent key already filled in. Extract to `C:\Program Files\Detec\`, copy `collector.json` to `%PROGRAMDATA%\Detec\`, and install the service. No manual setup required. Admins can also email a download link to end users directly from the dashboard.

**Option B: Manual setup.** After extracting the agent:

```powershell
# HTTP transport (default)
.\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY --interval 300

# TCP binary protocol (persistent connection to gateway on port 8001)
.\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY --interval 300 --protocol tcp
```

This writes `C:\ProgramData\Detec\Agent\agent.env` with the API URL, key, scan interval, and transport protocol.

**Option C: Pre-configured build.** Build the agent with config baked in:

```powershell
powershell -File packaging/windows/build-agent.ps1 -ApiUrl "http://server:8000/api" -ApiKey "YOUR_KEY"
```

### Install as a Windows Service

From an elevated (Administrator) command prompt:

```powershell
.\detec-agent.exe install
.\detec-agent.exe start
```

The service runs as "Detec Agent" and scans every 300 seconds (configurable). The first scan in a frozen bundle takes 90-120 seconds while all scanner modules load; the service reports `START_PENDING` to the SCM during this period.

### Manage the agent service

```powershell
.\detec-agent.exe stop      # stop the service
.\detec-agent.exe start     # start the service
.\detec-agent.exe remove    # unregister the service
.\detec-agent.exe status    # show config and service status
```

### Data locations

| Item | Path |
|------|------|
| Config | `C:\ProgramData\Detec\Agent\agent.env` |
| Logs | Windows Event Log (Application, source "DetecAgent") |
| Scan buffer | `C:\ProgramData\Detec\Agent\buffer.ndjson` (offline events queued for retry) |
