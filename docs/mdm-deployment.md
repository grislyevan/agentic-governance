# MDM Deployment Guide for Detec Agent

This guide covers deploying the Detec endpoint agent to managed macOS
devices using Jamf Pro, ManageEngine Endpoint Central, or any MDM that
supports `.pkg` distribution.

## Pre-Deployment Checklist

Before deploying to your fleet, ensure the following:

- [ ] Central API server is running and reachable from endpoint networks
- [ ] A tenant agent key exists (auto-generated on first agent download or server seed)
- [ ] Network firewall rules allow endpoints to reach the API server
      (port 443 for production HTTPS, 8000 for development HTTP,
      port 8001 for TCP binary protocol when using `--protocol tcp`)
- [ ] The `.pkg` installer has been built (`packaging/macos/build-pkg.sh`)
- [ ] (Recommended) The `.app` is code-signed with a Developer ID certificate
- [ ] (Recommended) The `.pkg` is signed with a Developer ID Installer certificate
- [ ] (Recommended) The `.app` has been notarized with Apple

## Deployment Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Installer package | `dist/DetecAgent-<version>.pkg` | Installs .app and configures LaunchAgent |
| PPPC profile | `packaging/macos/pppc-detec-agent.mobileconfig` | Pre-authorizes Full Disk Access |
| Configuration | `~/.agentic-gov/config.json` (per-user) | API URL, key, scan interval |

## Configuration Delivery

The agent needs two values at minimum: `api_url` and `api_key`. There
are several ways to deliver these to managed endpoints:

### Option 0: Pre-configured package from the server (recommended)

Build the `.pkg` with the server URL and tenant agent key baked in. The postinstall script copies the config to `~/Library/Application Support/Detec/agent.env` automatically; no additional MDM scripts or profiles needed.

**From the dashboard:** Go to Settings > Deploy Agent, select macOS, and click "Download Agent". The zip contains a `.pkg` with embedded config plus standalone `agent.env` and `collector.json` files. The tenant agent key is embedded automatically. You can also email a download link directly to end users from the same section.

**From the build machine:**

```bash
API_URL="https://detec-api.yourorg.com/api" API_KEY="YOUR_FLEET_KEY" bash packaging/macos/build-pkg.sh
```

Upload the resulting `.pkg` to your MDM for distribution. Agents connect automatically after install.

### Option 1: Config file via MDM script

Deploy a script that writes the config file before or after installation:

```bash
#!/bin/bash
CONFIG_DIR="$HOME/.agentic-gov"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/config.json" << 'EOF'
{
    "api_url": "https://detec-api.yourorg.com",
    "api_key": "YOUR_FLEET_API_KEY",
    "interval": 300,
    "sensitivity": "Tier1"
}
EOF
chmod 600 "$CONFIG_DIR/config.json"
```

### Option 2: Environment variables via LaunchAgent

Modify the LaunchAgent plist to include environment variables. Deploy a
custom plist via MDM instead of relying on the postinstall script:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>AGENTIC_GOV_API_URL</key>
    <string>https://detec-api.yourorg.com</string>
    <key>AGENTIC_GOV_API_KEY</key>
    <string>YOUR_FLEET_API_KEY</string>
</dict>
```

### Option 3: macOS Keychain

Store the API key in the macOS Keychain with the service name
`detec-agent` and account `api-key`. This is the most secure option
for manual deployments. For MDM, use a Keychain configuration profile
or a deployment script:

```bash
security add-generic-password -s "detec-agent" -a "api-key" \
    -w "YOUR_API_KEY" -U
```

## Jamf Pro Deployment

### Step 1: Upload the Package

1. Navigate to **Settings > Computer Management > Packages**
2. Click **New** and upload `DetecAgent-<version>.pkg`
3. Set Display Name: "Detec Agent"
4. Set Category: "Security" or "Endpoint Management"

### Step 2: Create the PPPC Profile

1. Navigate to **Computers > Configuration Profiles**
2. Click **New** and select **Privacy Preferences Policy Control**
3. Add an entry:
   - Identifier Type: Bundle ID
   - Identifier: `com.detec.agent`
   - Code Requirement: `identifier "com.detec.agent" and anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] and certificate leaf[field.1.2.840.113635.100.6.1.13] and certificate leaf[subject.OU] = "YOUR_TEAM_ID"`
   - SystemPolicyAllFiles: Allow
4. Scope to target computers/groups

Alternatively, upload the pre-built `pppc-detec-agent.mobileconfig`
profile directly (edit the TEAM_ID_HERE placeholder first).

### Step 3: Create the Configuration Script

1. Navigate to **Settings > Computer Management > Scripts**
2. Create a script that writes the config file (see Option 1 above)
3. Set Priority: "After" (runs after the package installs)

### Step 4: Create the Deployment Policy

1. Navigate to **Computers > Policies**
2. Create a new policy:
   - Trigger: "Recurring Check-in" or "Enrollment Complete"
   - Frequency: "Once per computer"
   - Packages: Add "Detec Agent"
   - Scripts: Add the configuration script (Priority: After)
   - Scope: Target computers or smart groups
3. Enable the policy

### Step 5: Verify Deployment

After deployment, verify agents are reporting:

1. Check the Detec dashboard for new endpoint registrations
2. On a target Mac: `launchctl list | grep detec`
3. Check logs: `tail -f ~/Library/Logs/DetecAgent/agent.log`

## ManageEngine Endpoint Central

### Step 1: Create a Software Package

1. Navigate to **Software Deployment > Packages**
2. Click **Add Package** > **macOS** > **Custom Package**
3. Upload `DetecAgent-<version>.pkg`
4. Set Package Type: "PKG"
5. Installation command: `installer -pkg DetecAgent-<version>.pkg -target /`

### Step 2: Deploy the PPPC Profile

1. Navigate to **Configuration > Profiles > macOS**
2. Create a new profile with the PPPC payload
3. Upload `pppc-detec-agent.mobileconfig` or configure manually:
   - App Identifier: `com.detec.agent`
   - Service: SystemPolicyAllFiles
   - Access: Allow

### Step 3: Deploy Configuration

Use a post-deployment script to write the config file:

1. Navigate to **Software Deployment > Packages**
2. Add a script package that runs after the installer
3. Script content: write `config.json` (see Option 1 above)

### Step 4: Create the Deployment Configuration

1. Navigate to **Software Deployment > Deploy**
2. Select the Detec Agent package
3. Set deployment type: "Install"
4. Schedule: Immediate or at next check-in
5. Target: Select computer groups

## Generic MDM

For any MDM that supports `.pkg` distribution, the deployment involves
three components:

1. **Package**: Upload and deploy `DetecAgent-<version>.pkg`
2. **Configuration profile**: Deploy `pppc-detec-agent.mobileconfig`
   for Full Disk Access (requires code-signed app)
3. **Configuration script**: Deliver the API credentials via a
   post-install script or a separate config profile

The installer handles LaunchAgent setup automatically via the
postinstall script. No additional launchctl commands are needed.

## Upgrade Workflow

To push a new version:

1. Build the new `.pkg` with the updated version number
2. Upload to your MDM as a new package version
3. Deploy with the same policy/configuration (the preinstall script
   handles stopping the running agent and the postinstall script
   restarts it with the new version)
4. Config files are preserved across upgrades (the installer does
   not overwrite `~/.agentic-gov/config.json`)

## Uninstall Procedure

Deploy a script via MDM to uninstall:

```bash
#!/bin/bash
# Uninstall Detec Agent

PLIST_LABEL="com.detec.agent"

# Stop the agent
launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist" 2>/dev/null || true

# Remove LaunchAgent
rm -f "$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

# Remove application
rm -rf "/Applications/Detec Agent.app"

# Optionally remove state and config
# rm -rf "$HOME/.agentic-gov"
# rm -rf "$HOME/Library/Logs/DetecAgent"

echo "Detec Agent uninstalled."
```

## Post-Deployment Verification

After deployment, use these methods to verify agents are running:

### From the Detec Dashboard

- Navigate to **Endpoints** to see registered agents
- Verify heartbeat timestamps are current
- Check for detection events from newly deployed endpoints

### From the Endpoint

```bash
# Check if the LaunchAgent is loaded
launchctl list | grep com.detec.agent

# Check the process
pgrep -fl "detec-agent"

# View recent logs
tail -20 ~/Library/Logs/DetecAgent/agent.log

# Verify API connectivity
curl -s -H "X-Api-Key: YOUR_KEY" https://your-api-server/health
```

### From the API

```bash
# List all endpoints
curl -s -H "X-Api-Key: YOUR_KEY" https://your-api-server/endpoints | python3 -m json.tool

# Check a specific endpoint's last heartbeat
curl -s -H "X-Api-Key: YOUR_KEY" https://your-api-server/endpoints | \
    python3 -c "import json,sys; [print(e['hostname'], e.get('last_heartbeat_at','never')) for e in json.load(sys.stdin).get('items',[])]"
```

## Network Requirements

Ensure the following network access from managed endpoints:

| Destination | Port | Protocol | Purpose |
|---|---|---|---|
| API server | 443 (prod) / 8000 (dev) | HTTPS/HTTP | Event submission, heartbeats |
| Gateway | 8001 | TCP (binary) | Persistent agent connection (when `--protocol tcp`) |
| DNS | 53 | UDP/TCP | Resolve API server hostname |

The agent does not require inbound connections. All communication is
initiated by the agent to the central API server. The TCP binary
protocol gateway port (8001) is only required when agents are configured
with `--protocol tcp`.
