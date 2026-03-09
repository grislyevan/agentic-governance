# Windows Server Packaging

Build and install the Detec server as a Windows Service.

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
