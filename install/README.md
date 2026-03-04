# Endpoint Agent — Install Guide

The agentic-gov endpoint agent runs the scanner continuously in the background, sending events to the central API over HTTP.

---

## Prerequisites

- Python 3.11+
- The `collector/` package installed or on `PYTHONPATH`
- An API key from the SaaS dashboard (or a locally-running API with `POST /events` and `POST /endpoints/heartbeat`)

---

## Quick start (foreground, any OS)

```bash
cd /path/to/agentic-governance
python -m collector.main \
  --api-url http://localhost:8000 \
  --api-key YOUR_API_KEY \
  --interval 300 \
  --sensitivity Tier1
```

Flags:

| Flag | Default | Description |
|---|---|---|
| `--api-url` | — | Central API base URL (required for daemon mode) |
| `--api-key` | — | API key header `X-Api-Key` (required for daemon mode) |
| `--interval` | `0` | Scan every N seconds; `0` = one-shot |
| `--sensitivity` | `Tier0` | Asset tier: Tier0–Tier3 |
| `--report-all` | off | Emit every detection every cycle (default: changes only) |
| `--verbose` | off | Print detailed scan progress |

---

## macOS — LaunchAgent

1. Edit `macos/ai.agentic-gov.agent.plist`:
   - Set `AGENTIC_GOV_API_URL` to your API endpoint.
   - Set `AGENTIC_GOV_API_KEY` to your key.
   - Adjust `PYTHONPATH` and the Python interpreter path.

2. Install and start:

```bash
cp install/macos/ai.agentic-gov.agent.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/ai.agentic-gov.agent.plist
```

3. Verify it is running:

```bash
launchctl list | grep agentic-gov
tail -f /tmp/agentic-gov-agent.log
```

4. Uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/ai.agentic-gov.agent.plist
rm ~/Library/LaunchAgents/ai.agentic-gov.agent.plist
```

---

## Linux — systemd (per-user, no root required)

1. Create an environment file:

```bash
mkdir -p ~/.config/agentic-gov
cat > ~/.config/agentic-gov/agent.env <<'EOF'
AGENTIC_GOV_API_URL=http://localhost:8000
AGENTIC_GOV_API_KEY=YOUR_API_KEY
AGENTIC_GOV_INTERVAL=300
AGENTIC_GOV_SENSITIVITY=Tier1
EOF
chmod 600 ~/.config/agentic-gov/agent.env
```

2. Install the unit file:

```bash
mkdir -p ~/.config/systemd/user/
cp install/linux/agentic-gov-agent.service ~/.config/systemd/user/
# Edit WorkingDirectory and ExecStart paths to match your install location
```

3. Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now agentic-gov-agent.service
```

4. Check status and logs:

```bash
systemctl --user status agentic-gov-agent
journalctl --user -u agentic-gov-agent -f
```

5. Uninstall:

```bash
systemctl --user disable --now agentic-gov-agent.service
rm ~/.config/systemd/user/agentic-gov-agent.service
systemctl --user daemon-reload
```

---

## Linux — systemd (system-wide, requires root)

```bash
sudo cp install/linux/agentic-gov-agent.service /etc/systemd/system/
sudo mkdir -p /etc/agentic-gov
sudo tee /etc/agentic-gov/agent.env > /dev/null <<'EOF'
AGENTIC_GOV_API_URL=http://localhost:8000
AGENTIC_GOV_API_KEY=YOUR_API_KEY
EOF
sudo chmod 600 /etc/agentic-gov/agent.env
sudo systemctl daemon-reload
sudo systemctl enable --now agentic-gov-agent.service
```

---

## Local state and buffer

The agent stores two files under `~/.agentic-gov/`:

| File | Purpose |
|---|---|
| `state.json` | Last-emitted state per tool (survives restarts) |
| `buffer.ndjson` | Events queued while the server was unreachable |

Both are created automatically on first run. Delete `state.json` to force a full re-report on the next cycle.

---

## Reporting modes

| Mode | Flag | Behaviour |
|---|---|---|
| **Changes only** (default) | _(none)_ | Emit events only when tool class, policy decision, or confidence band changes |
| **Report all** | `--report-all` | Emit all detections every cycle regardless of prior state |

Use `--report-all` during initial deployment or troubleshooting. Switch to the default changes-only mode for steady-state operation to minimise API traffic.
