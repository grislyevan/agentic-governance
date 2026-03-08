# Deploying the Detec Agent

This guide covers installing and running the **Detec Agent** (endpoint collector) so it reports to the central API. For deploying the **central server** (API + PostgreSQL), see [SERVER.md](SERVER.md). For collector configuration reference, see [collector/README.md](collector/README.md).

## Prerequisites

- **Python 3.11+** and **pip**
- **API URL** and **API key** from your central Detec API or dashboard. The API key is tied to a tenant; use the same key for all agents in that tenant.

## Install

From the repository root:

```bash
pip install -e .
```

This installs the **detec-agent** console script. Verify:

```bash
detec-agent --help
```

## Config (daemon mode)

For the agent to run as a persistent daemon and send events to the API, it needs at least:

- **interval** — how often to scan (e.g. `300` seconds)
- **api_url** — base URL of the central API (e.g. `https://api.example.com`)
- **api_key** — API key for authentication

You can provide these via:

1. **CLI:** `detec-agent --interval 300 --api-url https://api.example.com --api-key YOUR_KEY`
2. **Environment variables:** `AGENTIC_GOV_INTERVAL`, `AGENTIC_GOV_API_URL`, `AGENTIC_GOV_API_KEY`
3. **Config file:** `collector/config/collector.json` (see [collector/README.md](collector/README.md))

Do not commit API keys to config files in version control. For production, prefer environment variables or a secure credential store (see below).

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

Optional one-shot checks (if the API is on `localhost:8000` and you have an API key):

```bash
# Heartbeat (agent sends these periodically)
curl -s -X POST http://localhost:8000/endpoints/heartbeat \
  -H "X-Api-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"endpoint_id":"test","interval_seconds":300}'

# List endpoints (dashboard or API)
curl -s -H "X-Api-Key: YOUR_KEY" http://localhost:8000/endpoints
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
