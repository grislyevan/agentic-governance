# Deploying the Detec Agent

This guide covers installing and running the **Detec Agent** (endpoint collector) so it reports to the central API. For deploying the **central server** (API + PostgreSQL), see [SERVER.md](SERVER.md). For collector configuration reference, see [collector/README.md](collector/README.md).

## Deployment Options

| Method | Use Case | Details |
|---|---|---|
| **Dashboard download** | Zero-touch: pre-configured package from the server | [Download from Dashboard](#download-from-dashboard) |
| `.pkg` installer | MDM-managed macOS fleets (Jamf, Endpoint Central) | [Packaged Deployment](#packaged-deployment-macos) |
| `.exe` Windows Service | Windows endpoints | [Windows Deployment](#windows-deployment) |
| `pip install` | Development, Linux, manual installs | [Manual Install](#manual-install) |
| CLI only (headless) | Servers, CI, containers | [Manual Install](#manual-install) |

## Download from Dashboard

The fastest way to deploy agents. The central server generates a zip bundle containing the platform installer plus pre-filled configuration, so the agent connects automatically after install with zero manual setup.

### Prerequisites

- A running Detec central server (see [SERVER.md](SERVER.md))
- A pre-built agent package placed in `dist/packages/` on the server:
  - macOS: `DetecAgent-latest.pkg` (or `DetecAgent.pkg`)
  - Windows: `detec-agent.zip`
  - Linux: `detec-agent-linux.tar.gz`
- An admin or owner account with an API key

### From the Dashboard UI

1. Log in to the Detec dashboard.
2. Go to **Settings**.
3. In the **Download Agent** section, select the target platform (macOS, Windows, or Linux).
4. Optionally adjust the scan interval and transport protocol.
5. Click **Download Agent**.
6. A zip file downloads containing the installer, `agent.env`, `collector.json`, and a platform-specific README.
7. Transfer the zip to the target machine, extract, and run the installer. The agent connects to the server automatically.

### Via the API

```bash
# Download a pre-configured macOS agent package
curl -O -J \
  -H "X-Api-Key: YOUR_ADMIN_API_KEY" \
  "https://your-server.example.com/api/agent/download?platform=macos"

# With custom interval and TCP protocol
curl -O -J \
  -H "X-Api-Key: YOUR_ADMIN_API_KEY" \
  "https://your-server.example.com/api/agent/download?platform=windows&interval=600&protocol=tcp"
```

Query parameters:
- `platform` (required): `macos`, `windows`, or `linux`
- `interval` (optional, default 300): scan interval in seconds (30-86400)
- `protocol` (optional, default `http`): `http` or `tcp`

The endpoint requires `X-Api-Key` authentication with an `owner` or `admin` role. The API key you provide is the key that gets embedded in the agent config.

### Building Pre-Configured Packages

You can also build pre-configured packages directly (useful for MDM or automated fleet deployment):

**macOS:**
```bash
API_URL="https://server.example.com/api" API_KEY="YOUR_KEY" bash packaging/macos/build-pkg.sh
```

**Windows:**
```powershell
powershell -File packaging/windows/build-agent.ps1 -ApiUrl "https://server.example.com/api" -ApiKey "YOUR_KEY"
```

When the environment variables (macOS) or parameters (Windows) are provided, the build scripts embed `agent.env` / `collector.json` into the installer. The postinstall script copies the config to the platform-specific location automatically. When the variables are not provided, behavior is unchanged (generic package, manual setup required).

## Packaged Deployment (macOS)

For managed macOS environments, the agent ships as a `.pkg` installer
that includes a GUI menu bar app, a LaunchAgent for auto-start, and all
Python dependencies bundled (no Python installation required on target machines).

### Building the Installer

```bash
# Install build dependencies
pip install -e ".[gui-mac]"
pip install pyinstaller

# Build the .app bundle
bash packaging/macos/build-app.sh

# Build the .pkg installer
bash packaging/macos/build-pkg.sh
```

The `.pkg` is written to `dist/DetecAgent-<version>.pkg`.

### What the Installer Does

1. Installs `Detec Agent.app` to `/Applications`
2. Creates a LaunchAgent (`com.detec.agent.plist`) in `~/Library/LaunchAgents/`
3. Creates directories: `~/.agentic-gov/`, `~/Library/Logs/DetecAgent/`, `~/Library/Application Support/Detec/`
4. Transfers ownership of all created files from root to the logged-in user (pkg scripts run as root)
5. Loads the LaunchAgent so the agent starts automatically at login

### MDM Deployment

For fleet deployment via Jamf Pro, ManageEngine Endpoint Central, or
other MDMs, see [docs/mdm-deployment.md](docs/mdm-deployment.md).

Deploy the PPPC profile (`packaging/macos/pppc-detec-agent.mobileconfig`)
alongside the `.pkg` to pre-authorize Full Disk Access.

### Configuring the Agent (macOS)

After installing the `.pkg`, configure the agent to connect to your central server:

```bash
# HTTP transport (default)
detec-agent setup --api-url http://server:8000/api --api-key YOUR_KEY --interval 300

# TCP binary protocol
detec-agent setup --api-url http://server:8000/api --api-key YOUR_KEY --interval 300 --protocol tcp
```

This writes `~/Library/Application Support/Detec/agent.env`, which the GUI app loads on startup. Then launch the app:

```bash
open "/Applications/Detec Agent.app"
```

Alternatively, store the API key in macOS Keychain:

```bash
security add-generic-password -s "detec-agent" -a "api-key" -w "YOUR_KEY" -U
```

### Uninstalling (macOS)

To completely remove the Detec Agent, run the uninstaller script:

```bash
sudo bash packaging/macos/uninstall.sh
```

This stops the agent, removes the app from `/Applications`, deletes the
LaunchAgent, config, logs, state directory, Keychain entry, and the
installer receipt.

### macOS Permissions

See [docs/macos-permissions.md](docs/macos-permissions.md) for a
complete guide to required permissions, troubleshooting, and MDM
configuration profiles.

## Windows Deployment

For Windows endpoints, the agent ships as a standalone `.exe` that runs as a Windows Service (headless) or as a system tray app with a status window (GUI mode). No Python installation required on target machines.

### Building the Agent

On a build machine with Python 3.11+ and pip:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/build-agent.ps1
```

This produces `packaging/windows/dist/detec-agent/` containing `detec-agent.exe` and all dependencies.

### Installing on a Windows Endpoint

1. Copy the `detec-agent/` folder to the target machine (e.g., `C:\Program Files\Detec\`).

2. Configure the agent (from an elevated prompt):

```powershell
# HTTP transport (default)
.\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY

# TCP binary protocol
.\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY --protocol tcp
```

3. Install and start the Windows Service:

```powershell
.\detec-agent.exe install
.\detec-agent.exe start
```

The agent scans every 300 seconds by default and reports to the central server. It survives logoff and starts automatically on boot.

**Note:** The first scan in a frozen PyInstaller bundle takes approximately 90-120 seconds while all scanner modules are loaded. The service reports `START_PENDING` to the SCM with a 120-second wait hint during this period. Subsequent scans complete faster.

### GUI Mode (Windows tray app)

For interactive use, build and run the GUI tray agent instead:

```powershell
# Build
pip install pystray Pillow
cd packaging\windows
pyinstaller --clean --noconfirm detec-agent-gui.spec

# Run (after setup)
.\dist\detec-agent-gui\detec-agent-gui.exe
```

This shows a Detec icon in the notification area. Right-click for scan controls. Double-click (or "Show Status Window") opens a branded status window showing connection state, version, and build number.

### Managing the Agent Service

```powershell
.\detec-agent.exe status    # show config and service state
.\detec-agent.exe stop      # stop the service
.\detec-agent.exe start     # restart the service
.\detec-agent.exe remove    # unregister the service
```

For full details, see [packaging/windows/README.md](packaging/windows/README.md).

---

## Manual Install

### Prerequisites

- **Python 3.11+** and **pip**
- **API URL** and **API key** from your central Detec API or dashboard. The API key is tied to a tenant; use the same key for all agents in that tenant. API keys are shown only once at creation (seed log or registration response) and stored as a hash; save the key when it is first displayed.

### Install

From the repository root:

```bash
# Headless agent only
pip install -e .

# With GUI support (macOS)
pip install -e ".[gui-mac]"

# With GUI support (Windows)
pip install -e ".[gui-win]"
```

This installs the **detec-agent** console script (and **detec-agent-gui**
for macOS GUI mode). Verify:

```bash
detec-agent --help
```

## Config (daemon mode)

For the agent to run as a persistent daemon and send events to the API, it needs at least:

- **interval** — how often to scan (e.g. `300` seconds)
- **api_url** — base URL of the central API (e.g. `https://server.example.com/api`)
- **api_key** — API key for authentication

You can provide these via:

1. **CLI:** `detec-agent --interval 300 --api-url https://server.example.com/api --api-key YOUR_KEY`
2. **Environment variables:** `AGENTIC_GOV_INTERVAL`, `AGENTIC_GOV_API_URL`, `AGENTIC_GOV_API_KEY`
3. **Config file:** `collector/config/collector.json` (see [collector/README.md](collector/README.md))

Do not commit API keys to config files in version control. For production, prefer environment variables or a secure credential store (see below).

### Transport protocol

By default, agents use **HTTP** (REST calls to `POST /api/events`). You can switch to the **TCP binary protocol** for lower overhead, persistent connections, and server-push capability (policy updates, remote commands):

```bash
# HTTP (default)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY

# TCP binary protocol (connects to gateway on port 8001)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY --protocol tcp

# TCP with custom gateway host/port
detec-agent --protocol tcp --gateway-host gateway.example.com --gateway-port 9001 --api-key YOUR_KEY
```

When using `--protocol tcp`, the agent derives `gateway_host` from the `api_url` hostname by default. Override with `--gateway-host` if the gateway runs on a different host. The TCP binary protocol requires `GATEWAY_ENABLED=true` on the server (see [SERVER.md](SERVER.md)).

Environment variables: `AGENTIC_GOV_PROTOCOL` (`http` or `tcp`), `AGENTIC_GOV_GATEWAY_HOST`, `AGENTIC_GOV_GATEWAY_PORT`.

## Auto-start at boot / logon

Templates are in **[deploy/](deploy/)**. Use the one for your platform.

### macOS (LaunchAgent)

1. Copy the plist and edit the API URL (and interval if desired):
   ```bash
   cp deploy/macos/com.detec.agent.plist ~/Library/LaunchAgents/
   # Edit ~/Library/LaunchAgents/com.detec.agent.plist: set your --api-url in ProgramArguments
   ```

2. Set the API key via environment (so it is not stored in the plist). For example, before loading the agent, run:
   ```bash
   launchctl setenv AGENTIC_GOV_API_KEY "your-api-key"
   ```
   Then load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.detec.agent.plist
   ```
   Alternatively, use macOS Keychain and the optional credentials module (see [Secure API key storage](#secure-api-key-storage-optional)).

3. Logs: `tail -f /tmp/detec-agent.log` and `/tmp/detec-agent.err`.

### Linux (systemd user unit)

1. Create the environment file with your API URL and key:
   ```bash
   mkdir -p ~/.config/detec
   echo 'AGENTIC_GOV_API_URL=https://api.example.com' >> ~/.config/detec/agent.env
   echo 'AGENTIC_GOV_API_KEY=your-api-key' >> ~/.config/detec/agent.env
   chmod 600 ~/.config/detec/agent.env
   ```

2. Install and start the user service:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp deploy/linux/detec-agent.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now detec-agent.service
   ```

3. Check status: `systemctl --user status detec-agent.service`.

### Windows (scheduled task)

1. Install the package so `detec-agent` is on PATH (e.g. `pip install -e .` from the repo).

2. Set user or system environment variables:
   - `AGENTIC_GOV_API_URL` = your API base URL
   - `AGENTIC_GOV_API_KEY` = your API key

3. Create the task (run PowerShell as the user):
   ```powershell
   cd path\to\agentic-governance
   powershell -ExecutionPolicy Bypass -File deploy\windows\install-detec-agent-task.ps1
   ```
   The task runs at user logon. To run immediately: `Start-ScheduledTask -TaskName "Detec Agent"`.

## Verification

After the agent is running:

1. **Endpoint visible:** In the dashboard or via the API (e.g. `GET /endpoints`), confirm the endpoint appears (identified by hostname or configured `endpoint_id`).

2. **Events flowing:** After at least one scan cycle (within the configured interval), detection events should appear for that endpoint.

Optional one-shot checks (if the server is on `localhost:8000` and you have an API key):

```bash
# Heartbeat (agent sends these periodically)
curl -s -X POST http://localhost:8000/api/endpoints/heartbeat \
  -H "X-Api-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"endpoint_id":"test","interval_seconds":300}'

# List endpoints (dashboard or API)
curl -s -H "X-Api-Key: YOUR_KEY" http://localhost:8000/api/endpoints
```

## One agent per user vs per machine

By default, the agent runs as the **logged-in user** and stores state under `~/.agentic-gov/state.json`. That gives one agent per user on the machine.

For **one agent per machine**, run the service as system/root (e.g. install the systemd unit under `/etc/systemd/system/` and run as root, or a dedicated service account). Then set `endpoint_id` and `actor_id` as needed (e.g. same endpoint_id for the machine, actor_id for the service account). Document the tradeoff in your deployment: per-user gives per-user visibility; per-machine simplifies inventory.

## Secure API key storage (optional)

For production, store the API key in the OS credential store and do not pass it via config file or plist. The agent tries the platform store first when `api_key` is not set:

- **macOS:** Keychain — store with: `security add-generic-password -s detec-agent -a api-key -w YOUR_KEY`. The agent reads it automatically when no env/config key is set.
- **Windows:** Credential Manager — create a generic credential with target name `detec-agent` (e.g. Control Panel → Credential Manager → Windows Credentials → Add a generic credential).
- **Linux:** `secret-tool` (libsecret) — store with: `secret-tool store service detec-agent account api-key` (then paste the key). Or create `~/.config/detec/api_key` with mode `600` and the key as contents.

If no key is found in the store, the agent falls back to environment variable or config file.

## Enforcement caveats

### Network blocking on Linux

When a policy triggers `network_block` enforcement, the agent uses `iptables --uid-owner` to drop outbound packets. Modern Linux kernels no longer support `--pid-owner`, so this blocks **all** processes owned by the target UID, not just the target tool. If the tool runs under a shared user account, this will affect the user's browser, IDE, shell, and everything else until the rule is removed.

Mitigations:
- Run high-risk tools under a dedicated service account so UID-scoped blocking is isolated.
- Use `dry_run: true` when evaluating network enforcement to observe what would be blocked.
- The agent logs a WARNING when UID-scoped blocking is applied.

### Process kill and PID reuse

When a policy triggers `process_kill`, the agent verifies the process command line matches the expected tool pattern before sending signals. This prevents accidental kills from PID reuse. If the command line cannot be read (e.g., on macOS without Full Disk Access), the kill is skipped and logged.

## Deployment Directory Layout

| Directory | Purpose |
|---|---|
| `packaging/macos/` | Build scripts, PyInstaller spec, .pkg config, PPPC profile, and uninstaller for macOS packaged deployment |
| `deploy/` | Platform-specific LaunchAgent/systemd/task templates for manual installs |
| `docs/` | Permissions guide, MDM deployment guide |
| `install/` | (Deprecated) Legacy install scripts; use `deploy/` or `packaging/` instead |
