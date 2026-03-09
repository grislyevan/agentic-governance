# Windows Packaging

Build and install Detec components as Windows Services.

## Quick Build

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
```

This generates a `server.env` in `C:\ProgramData\Detec\` with a random JWT secret and seed admin password. Save the password shown on screen.

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

The service runs as "Detec Server" and starts automatically on boot. The server is accessible at http://localhost:8000.

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
| Logs | Windows Event Log (Application, source "DetecServer") |

### Backup

Copy `C:\ProgramData\Detec\detec.db` while the service is running (SQLite WAL mode supports hot copies). For a consistent snapshot, stop the service first.

### Firewall

If agents connect from other machines, allow inbound TCP on port 8000:

```powershell
New-NetFirewallRule -DisplayName "Detec Server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Detec Agent (Collector)

### Quick Build

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build-agent.ps1
```

This produces `packaging/windows/dist/detec-agent/` containing `detec-agent.exe`.

### One-shot scan (testing)

```powershell
cd dist\detec-agent
.\detec-agent.exe scan --verbose
```

### Configure the agent

```powershell
.\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY --interval 300
```

This writes `C:\ProgramData\Detec\Agent\agent.env` with the API URL, key, and scan interval.

### Install as a Windows Service

From an elevated (Administrator) command prompt:

```powershell
.\detec-agent.exe install
.\detec-agent.exe start
```

The service runs as "Detec Agent" and scans every 300 seconds (configurable).

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
