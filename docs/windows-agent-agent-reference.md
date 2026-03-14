# Windows Agent Reference

This document is a single reference for the Detec Windows endpoint agent: how it ties to the server, how it communicates, what it can do, how to install it, and where to find more detail.

## How the agent ties to the Detec server

The agent is tied to a tenant on the Detec server by configuration that contains:

- **API URL** (e.g. `http://server:8000/api`)
- **Tenant agent key** (a shared secret for that tenant)

That configuration is stored in:

- `C:\ProgramData\Detec\Agent\agent.env`
- `C:\ProgramData\Detec\Agent\collector.json`

**When you download from the dashboard:** You get a zip containing `DetecAgentSetup.exe`, `agent.env`, and `collector.json`. Extract the zip and run the installer from the same folder. The installer copies those config files into `ProgramData\Detec\Agent` so the agent connects to your server with no manual setup (zero-touch). You can also pass `/CONFIGDIR=path` to point to a folder that contains the config files.

**Manual setup:** If there is no config (e.g. you run a generic installer without sidecar files), install the agent and then run:

```text
detec-agent setup --api-url <URL> --api-key <KEY> --interval 300
```

That writes the same config files so the agent is tied to your tenant.

## How the agent communicates with the server

- **HTTP (default):** The agent sends events to `POST /api/events` and heartbeats to `POST /api/endpoints/heartbeat`, using the API URL and tenant agent key from config.
- **TCP (optional):** With `protocol` set to `tcp` in config, the agent keeps a persistent connection to the gateway (default port 8001) and sends events and heartbeats over that channel. The server can push policy and commands over the same connection.

## Admin-level capabilities and enforcement

The agent does not manage the Detec server or other endpoints. On the endpoint where it runs:

- When the server sets the endpoint to **active** enforcement posture, the agent can **kill processes** (blocked tool processes, with a short grace period) and **block outbound network** for those processes (on Windows via `netsh advfirewall`).
- Install and uninstall require **admin** (elevation). Stopping or removing the Detec Agent service is restricted to administrators (see [tamper-controls.md](tamper-controls.md)).

So the agent can perform local enforcement (process kill and network block) when the server configures it to do so; it does not give the server arbitrary admin on the machine beyond that.

## Can the agent block, stop, or kill processes?

- **Kill/stop:** Yes. When enforcement is active and policy says block, the enforcer terminates the process (graceful then force after a short delay). Implemented in `collector/enforcement/process_kill.py` and works on Windows.
- **Block (network):** Yes. Outbound blocking for blocked PIDs is supported on Windows via `netsh advfirewall` in `collector/enforcement/network_block.py`.

## Install process

1. Get the Windows agent package (zip with `DetecAgentSetup.exe` plus config) from the dashboard or an enrollment link.
2. Extract the zip and run `DetecAgentSetup.exe` (as administrator).
3. The installer extracts files to `C:\Program Files\Detec\Agent\`, applies config from the same folder (or `/CONFIGDIR`), runs `detec-agent.exe install-service` (install, start, and failure recovery in one step), and optionally launches the system tray and adds it to Run for the current user.
4. The **Detec Agent** Windows Service is set to start automatically and loads config from `C:\ProgramData\Detec\Agent\`.

There are no wizard pages; a single progress screen is shown, then the installer closes. An install log is written to `C:\ProgramData\Detec\Agent\install.log`.

## Silent install and system tray

- **Silent install:** Use `/VERYSILENT` for a fully headless install. The tray app is not launched during a silent install unless you request it.
- **Tray after silent install:** Use `/VERYSILENT /LAUNCHTRAY=1` to install silently and still start the tray so status is visible without a reboot. Otherwise the tray is registered in HKCU Run and will start at the next user logon.
- **Service only (no tray):** Use `/NOTRAY=1` to install the Windows Service without adding the tray to Run and without launching it (e.g. for headless servers).

## Streamlining and improvement areas

- **Single install step:** The installer uses `detec-agent.exe install-service` to register the service, start it, and set failure recovery in one call (see [packaging/windows/README.md](../packaging/windows/README.md)).
- **Config without EXE modification:** Config is delivered in the same zip as the installer (or via `/CONFIGDIR`). The EXE is not modified, which allows code signing and reduces AV false positives.
- **Optional tray:** `/NOTRAY=1` avoids tray and Run key for server/MDM deployments.

For more detail on install behavior, failure modes, and QA, see [windows-install-failure-notes.md](windows-install-failure-notes.md). For zero-touch deployment and download endpoints, see [zero-touch-deployment-summary.md](zero-touch-deployment-summary.md).
