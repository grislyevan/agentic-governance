# Deploying the Detec Agent

This guide covers installing and running the **Detec Agent** (endpoint collector) so it reports to the central API. For deploying the **central server** (API + PostgreSQL), see [SERVER.md](SERVER.md). For collector configuration reference, see [collector/README.md](collector/README.md).

## Deployment Options

| Method | Use Case | Details |
|---|---|---|
| **Dashboard download** | Zero-touch: pre-configured package from the server | [Download from Dashboard](#download-from-dashboard) |
| `.exe` Windows Service | Windows endpoints | [Windows Deployment](#windows-deployment) |
| `pip install` | macOS dev, Linux, manual installs | [Manual Install](#manual-install) |
| CLI only (headless) | Servers, CI, containers | [Manual Install](#manual-install) |

## Running the agent against local Docker

Use this when the API (and optional dashboard) are running via Docker Compose and you want the scanner on your host to report to it.

1. **Start the stack** (from repo root):
   ```bash
   docker compose up -d
   ```
   API is at `http://localhost:8000`, dashboard at `http://localhost:3001` (or use the API root at `http://localhost:8000` if the API serves the built dashboard).

2. **Get the agent key** (tenant key the agent uses to authenticate):
   - **Option A:** Before first run, set `SEED_AGENT_KEY` in `.env` to a known value (e.g. `openssl rand -hex 32`). The seed tenant will use it; use the same value when running the agent.
   - **Option B:** If the stack was already seeded, run `docker compose logs api` and look for the line `agent_key: <value>` in the initial seed output. Copy that value.
   - **Option C:** Log in to the dashboard as admin, go to **Settings**, use **Rotate agent key** (if available); the new key is shown once in the response. Or call `POST /api/agent/key/rotate` with your JWT/API key; the response body contains `agent_key`.

3. **Install the collector** (from repo root):
   ```bash
   pip install -e .
   ```
   This installs the `detec-agent` CLI.

4. **Run the agent** (one-shot or daemon):
   ```bash
   detec-agent \
     --api-url http://localhost:8000/api \
     --api-key YOUR_AGENT_KEY \
     --interval 300 \
     --report-all
   ```
   Omit `--report-all` to send only change events. Use `--dry-run --verbose` to test the scan without sending to the API.

   You can also set `AGENTIC_GOV_API_URL` and `AGENTIC_GOV_API_KEY` in the environment instead of CLI flags.

5. **Confirm in the dashboard:** Open the dashboard, go to the main inventory or Endpoints view; the endpoint should appear and events should flow after the first scan and heartbeat.

## Download from Dashboard

The fastest way to deploy agents. The central server generates a zip bundle containing the platform installer plus pre-filled configuration, so the agent connects automatically after install with zero manual setup.

### Prerequisites

- A running Detec central server (see [SERVER.md](SERVER.md))
- A pre-built agent package available to the server:
  - **Docker:** copy Windows and Linux installers into `docker/default-agent-packages/` then rebuild the **api** image. See [SERVER.md](SERVER.md) Agent downloads.
  - **Bare metal:** place files in `dist/packages/` (Windows: `detec-agent.zip`; Linux: `detec-agent-linux.tar.gz`).
- An admin or owner account (login via email/password or API key)

### From the Dashboard UI

1. Log in to the Detec dashboard.
2. Go to **Settings**.
3. In the **Deploy Agent** section, select **Windows** or **Linux**.
4. Optionally adjust the scan interval and transport protocol.
5. Click **Download** to fetch a pre-configured zip bundle.
6. Transfer the file to target machines (email, MDM, shared drive).
7. The agent connects automatically after install. No manual API key handling.

**macOS:** There is no packaged macOS agent download. Run the collector from source on Mac (`pip install -e .`, then `detec-agent`). See [Manual Install](#manual-install).

The server automatically generates and manages a tenant-level agent key. No manual API key handling is required.

### Email Enrollment

Admins can send a download link directly to end users:

1. In the **Deploy Agent** section, enter the user's email address.
2. Click **Send Download Link**.
3. The user receives an email with a one-click download link (valid for 72 hours, single-use).
4. The user clicks the link, downloads the pre-configured package, and installs it.

Email enrollment requires SMTP configuration on the server. See [SERVER.md](SERVER.md) for SMTP settings.

### Via the API

```bash
# Download (JWT auth via cookie or Bearer token)
curl -O -J \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "https://your-server.example.com/api/agent/download?platform=windows"

# Download (API key auth also works)
curl -O -J \
  -H "X-Api-Key: YOUR_ADMIN_API_KEY" \
  "https://your-server.example.com/api/agent/download?platform=linux"

# Email a download link to a user
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@company.com", "platform": "windows"}' \
  "https://your-server.example.com/api/agent/enroll-email"
```

Query parameters for download:
- `platform` (required): `windows` or `linux`
- `interval` (optional, default 300): scan interval in seconds (30-86400)
- `protocol` (optional): omit to use server default (**`http`**, works when only API port 8000 is exposed, e.g. Docker Compose). Or set `auto` (TCP first on gateway port 8001, then HTTP), `tcp`, or `http` explicitly.

The download endpoint requires `owner` or `admin` role. The server embeds the tenant's agent key in the package automatically.

### Building Pre-Configured Packages

You can also build pre-configured packages directly (useful for MDM or automated fleet deployment):

**Windows:**
```powershell
powershell -File installers/windows/build-agent.ps1 -ApiUrl "https://server.example.com/api" -ApiKey "YOUR_KEY"
```

When build parameters are provided, the Windows script can embed config. When omitted, use a generic package and configure manually.

## macOS (development)

There is no shipped macOS installer or dashboard download. On Apple Silicon or Intel Macs used for development, install from the repo root with `pip install -e .`, set `AGENTIC_GOV_API_URL` / `AGENTIC_GOV_API_KEY` (or use flags), and run `detec-agent`. Scanner behavior and permissions on macOS are covered in [docs/macos-permissions.md](docs/macos-permissions.md). For MDM-focused notes on Mac dev machines, see [docs/mdm-deployment.md](docs/mdm-deployment.md).

## Windows Deployment

For Windows endpoints, the agent ships as a standalone `.exe` that runs as a Windows Service (headless) or as a system tray app with a status window (GUI mode). No Python installation required on target machines.

### Building the Agent

On a build machine with Python 3.11+ and pip:

```powershell
powershell -ExecutionPolicy Bypass -File installers/windows/build-agent.ps1
```

This produces `installers/windows/dist/detec-agent/` containing `detec-agent.exe` and all dependencies.

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
cd installers\windows
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

For full details, see [installers/windows/README.md](installers/windows/README.md).

---

## Manual Install

### Prerequisites

- **Python 3.11+** and **pip**
- **API URL** and **API key** from your central Detec API or dashboard. The API key is tied to a tenant; use the same key for all agents in that tenant. API keys are shown only once at creation (seed log or registration response) and stored as a hash; save the key when it is first displayed.

### Install

From the repository root:

```bash
# Collector CLI (macOS, Linux, Windows)
pip install -e .

# Optional: Windows tray dev deps (shipped agent uses PyInstaller)
pip install -e ".[gui-win]"
```

This installs the **detec-agent** console script. Verify:

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

**Auto** (default): the agent tries the **TCP binary protocol** first, then uses **HTTP** if the gateway is unreachable. Use **TCP only** for strict binary transport, or **HTTP only** if port 8001 is never available (for example serverless). TCP gives lower overhead, persistent connections, and server-push (policy updates, remote commands). On HTTP fallback, server-push commands are not delivered until TCP works again.

```bash
# Auto: TCP first, HTTP fallback (default)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY

# TCP only (fails closed if gateway down)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY --protocol tcp

# HTTP only
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY --protocol http

# Custom gateway host/port (for auto or tcp)
detec-agent --gateway-host gateway.example.com --gateway-port 9001 --api-key YOUR_KEY
```

`gateway_host` defaults to the hostname from `api_url`. The server must run the gateway for TCP (`GATEWAY_ENABLED=true`; see [SERVER.md](SERVER.md)).

Environment variables: `AGENTIC_GOV_PROTOCOL` (`auto`, `http`, or `tcp`), `AGENTIC_GOV_GATEWAY_HOST`, `AGENTIC_GOV_GATEWAY_PORT`. Optional tuning: `AGENTIC_GOV_TCP_CONNECT_TIMEOUT_SECONDS`, `AGENTIC_GOV_TCP_RETRY_INTERVAL_SECONDS`, `AGENTIC_GOV_TCP_FAILURE_THRESHOLD`, `AGENTIC_GOV_TCP_RECOVERY_STABILITY_SECONDS`. JSON may use `tcp_host` / `tcp_port` as aliases for `gateway_host` / `gateway_port`.

### Telemetry provider

The agent supports pluggable telemetry providers that control how process and network data is collected. Currently only the polling provider (psutil snapshots) is available; native OS providers (macOS ESF, Windows ETW, Linux eBPF) will be added in future releases.

```bash
# Default: auto-detect best available provider (currently always polling)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY

# Force polling only (useful for testing or constrained environments)
detec-agent --interval 300 --api-url http://server:8000/api --api-key YOUR_KEY --telemetry-provider polling
```

Environment variable: `AGENTIC_GOV_TELEMETRY_PROVIDER` (`auto`, `native`, or `polling`).

## Auto-start at boot / logon

Templates are in **[deploy/](deploy/)**. Use the one for your platform.

### macOS (manual LaunchAgent, optional)

For a **per-user LaunchAgent** (development or manual installs):

1. Copy the sample plist and edit the API URL (and interval if desired):
   ```bash
   cp install/macos/ai.agentic-gov.agent.plist ~/Library/LaunchAgents/
   # Edit ~/Library/LaunchAgents/ai.agentic-gov.agent.plist: set your --api-url in ProgramArguments
   ```

2. Set the API key via environment (so it is not stored in the plist). For example, before loading the agent, run:
   ```bash
   launchctl setenv AGENTIC_GOV_API_KEY "your-api-key"
   ```
   Then load the agent:
   ```bash
   launchctl load -w ~/Library/LaunchAgents/ai.agentic-gov.agent.plist
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

## Pre-deployment checklist

The following items must be completed before a production deployment. They are not required for local development or pre-deploy testing.

### 1. Set `ALLOWED_RETURN_ORIGINS` (Stripe billing)

The Stripe checkout and billing portal redirect URLs are validated against this setting. If it is left empty, any URL is accepted (backward-compatible default, but unsafe in production).

Set it in your server `.env` or deployment environment to a comma-separated list of your app's origins:

```
ALLOWED_RETURN_ORIGINS=https://app.yourcompany.com,https://www.yourcompany.com
```

Requests with `success_url`, `cancel_url`, or `return_url` whose origin is not in this list will be rejected with HTTP 400.

### 2. Rotate all tenant agent keys (hashing migration)

Migration `0019_hash_agent_keys` runs automatically on `alembic upgrade head` and hashes any existing plaintext agent keys in-place. However, the hashed keys are derived from the old plaintext values using SHA-256 — they are not new random keys.

After deploying, each tenant should rotate their agent key via the dashboard (**Settings → Rotate agent key**) or the API:

```bash
curl -X POST https://your-server/api/agent/key/rotate \
  -H "Authorization: Bearer YOUR_JWT"
```

The response contains the new key (shown once). Redeploy agents with the new key. Until rotation, the pre-migration hashed keys continue to work via the plaintext fallback path in `resolve_auth()`.

---

## Deployment Directory Layout

| Directory | Purpose |
|---|---|
| `installers/windows/` | Windows PyInstaller spec, Inno Setup, build scripts |
| `deploy/` | Manual systemd / Windows Task templates (Linux and Windows) |
| `docs/` | Permissions guide, MDM deployment guide |
| `install/` | (Deprecated) Legacy install scripts; use `deploy/` or `installers/` instead |
