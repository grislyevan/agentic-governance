# macOS Permissions Guide for Detec Agent

The Detec endpoint agent requires specific macOS permissions to perform
comprehensive AI tool detection. This document covers what permissions
are needed, why, and how to grant them (both manually and via MDM).

## Permission Summary

| Permission | Required | Why | User Impact |
|---|---|---|---|
| Full Disk Access | Yes | Read application metadata, config files, and extension manifests across the filesystem | One-time prompt or MDM profile |
| Background Items | Yes (macOS 13+) | LaunchAgent runs at login | System notification on first load |
| Outgoing Network | Yes | POST detection events and heartbeats to the central API | Firewall prompt if Application Firewall is enabled |
| Process Inspection | Implicit | `psutil` reads the process list to detect running AI tools | Covered by standard user permissions |
| Keychain Access | Optional | Retrieve the API key from the macOS Keychain | Keychain prompt on first access (can be suppressed by MDM) |

## Full Disk Access (FDA)

**Why it's needed**: The agent's scanners inspect files in locations that
require elevated read access:

- `/Applications/` and `~/Applications/` for installed AI tool bundles
- `~/Library/Application Support/` for VS Code extensions, Cursor config,
  Claude data, and other tool state
- `/usr/local/` and `~/.local/` for CLI tools (Ollama, Aider, Open Interpreter)
- `~/.config/` for tool configuration files

Without FDA, some scanners will return incomplete results. The agent
never writes to these locations; it only reads metadata and config files.

### Granting Manually

1. Open **System Settings** (or System Preferences on older macOS)
2. Go to **Privacy & Security > Full Disk Access**
3. Click the lock icon and authenticate
4. Click **+** and navigate to `/Applications/Detec Agent.app`
5. Toggle the switch to enable

### Granting via MDM (PPPC Profile)

Deploy a Privacy Preferences Policy Control profile that pre-authorizes
FDA. See the template at `packaging/macos/pppc-detec-agent.mobileconfig`.

The key TCC entry:

```xml
<key>Authorization</key>
<string>AllowStandardUserToSetSystemService</string>
<key>CodeRequirement</key>
<string>identifier "com.detec.agent"</string>
<key>IdentifierType</key>
<string>bundleID</string>
<key>Services</key>
<dict>
    <key>SystemPolicyAllFiles</key>
    <dict>
        <key>Authorization</key>
        <string>Allow</string>
    </dict>
</dict>
```

**Important**: PPPC profiles require the app to be code-signed with a
Developer ID certificate. Unsigned apps cannot be pre-authorized via MDM.

## Background Items (macOS 13 Ventura+)

Starting with macOS 13, the system notifies users when a new login item
or LaunchAgent is added. The Detec Agent installer writes a LaunchAgent
plist to `~/Library/LaunchAgents/com.detec.agent.plist`.

**What the user sees**: A system notification saying "Detec Agent added
items that can run in the background." The user can manage this in
**System Settings > General > Login Items & Extensions**.

**MDM suppression**: MDM-managed devices can suppress this notification
by deploying the LaunchAgent via a configuration profile rather than
a postinstall script. Alternatively, the `com.apple.servicemanagement`
payload can be used to explicitly allow the background item.

## Outgoing Network Connections

The agent connects to the central server using one of two transports:

**HTTP transport** (default):
- `POST /events` to submit detection events
- `POST /endpoints/heartbeat` for status monitoring
- `GET /health` for connectivity checks

**TCP binary protocol** (when `--protocol tcp` is configured):
- Persistent connection to the DetecGateway for event ingestion, heartbeats, and server-push (policy updates, commands)

If the macOS Application Firewall (ALF) is enabled, the user may see
a prompt asking whether to allow outgoing connections from Detec Agent.
Code-signed applications are generally allowed automatically.

**Ports**: The agent connects to the API server's configured port
(typically 443 for production HTTPS, 8000 for development HTTP). When
using the TCP binary protocol, the agent also connects to port 8001
(configurable via `--gateway-port`).

**Firewall rule via MDM**: Add Detec Agent to the Application Firewall
allowlist using a `com.apple.alf` configuration profile payload.

## Process Inspection

The agent uses `psutil` to enumerate running processes and identify AI
tool processes by name, command line, and network connections. This
operates within standard user permissions on macOS. No special
entitlement is required.

**What it reads**: Process names, PIDs, command-line arguments, network
connections (listening ports), and parent process chains.

**What it does NOT do**: The agent does not inject into processes, read
process memory, attach debuggers, or use any accessibility APIs.

## Keychain Access (Optional)

If the API key is stored in the macOS Keychain (service: `detec-agent`,
account: `api-key`), the agent reads it at startup. The user will see
a Keychain access prompt the first time unless:

- The Keychain item's ACL includes the Detec Agent binary
- An MDM profile pre-authorizes Keychain access

To avoid Keychain prompts entirely, configure the API key via the
config file (`~/.agentic-gov/config.json`) or environment variable
(`AGENTIC_GOV_API_KEY`) instead.

## Troubleshooting

### Agent reports fewer detections than expected

Check Full Disk Access. Without it, scanners that inspect
`~/Library/Application Support/` or `/Applications/` may fail silently.

Verify in System Settings > Privacy & Security > Full Disk Access.

### "Agent Status... Disconnected" in the menu bar

1. Check that `api_url` and `api_key` are configured in
   `~/.agentic-gov/config.json` or via environment variables
2. Verify network connectivity to the API server
3. Check `~/Library/Logs/DetecAgent/agent.log` for errors

### LaunchAgent not loading

```bash
# Check if the plist exists
ls -la ~/Library/LaunchAgents/com.detec.agent.plist

# Check if the agent is loaded
launchctl list | grep detec

# Load manually
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.detec.agent.plist

# Check for errors
launchctl print gui/$(id -u)/com.detec.agent
```

### Log file locations

| Log | Path |
|---|---|
| Agent output | `~/Library/Logs/DetecAgent/agent.log` |
| Agent errors | `~/Library/Logs/DetecAgent/agent-error.log` |
| LaunchAgent stdout | `~/Library/Logs/DetecAgent/agent.log` |
| State file | `~/.agentic-gov/state.json` |
| Buffered events | `~/.agentic-gov/buffer.ndjson` |
