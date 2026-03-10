# Windows Packaging

Build and install Detec components as Windows Services.

## GUI Installer (recommended for clients)

Ship a single `DetecServerSetup.exe` to clients. They double-click it and follow a branded wizard; no PowerShell required.

### Building the installer

On your build machine (requires Python 3.11+, Node.js 22+, and [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
```

This runs the full pipeline: dashboard build, PyInstaller bundle, branding asset generation, and Inno Setup compilation. Output: `packaging/windows/dist/DetecServerSetup-0.1.0.exe`.

### What the installer does

The wizard walks the user through these steps:

1. **License agreement**: accept the Detec Server EULA
2. **Pre-flight checks**: validates disk space (300 MB minimum), port availability, detects existing installations or services
3. **Server configuration**: choose the API port (default 8000) and database backend (SQLite or PostgreSQL with connection URL)
4. **Installation summary**: review chosen settings before proceeding
5. **File extraction + post-install**: extracts the server bundle to `C:\Program Files\Detec\Server\`, generates secrets and an `admin@localhost` administrator account, installs and starts the Windows Service, configures the firewall, and creates a desktop shortcut
6. **Credentials page**: displays the generated admin password (shown once, user must save it)
7. **Finish page**: includes an "Open Detec Dashboard" button

The installer also registers an uninstaller in Add/Remove Programs that stops the service, removes the service, cleans up the firewall rule, deletes files, and optionally removes the data directory (`C:\ProgramData\Detec\`).

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
