# MDM Deployment Guide (macOS — ESF Telemetry)

This guide covers deploying the Detec endpoint agent to a managed macOS fleet with the
Endpoint Security Framework (ESF) telemetry provider active. If you only need the
polling-based provider (no ESF), standard source installation is sufficient; see
[DEPLOY.md](../DEPLOY.md).

---

## 1. Overview

### What is ESF?

Apple's [Endpoint Security Framework](https://developer.apple.com/documentation/endpointsecurity)
(macOS 10.15+) is a kernel-level API that delivers real-time notifications for process
execution (`EXEC`), file opens (`OPEN`), and Unix-socket connections (`UIPC_CONNECT`).
The Detec agent uses a thin helper binary (`esf_helper`) to subscribe to these events and
forward them over a Unix domain socket to the main Python agent process.

### Why does ESF need special deployment?

ESF has two hard requirements that cannot be satisfied by a drag-and-drop install:

1. **Entitlement**: The helper binary must be code-signed with a Developer ID certificate
   that carries the `com.apple.developer.endpoint-security.client` entitlement. Apple
   grants this only to provisioned team accounts.
2. **Full Disk Access (TCC)**: macOS requires the signed binary to hold FDA before the
   ESF client can be created. On managed devices this is granted silently via an MDM
   Privacy Preferences Policy Control (PPPC) profile; on unmanaged devices the user must
   approve manually.

### What MDM enables vs. manual install

| | Manual install | MDM-managed |
|---|---|---|
| Full Disk Access | User approves in System Settings | Pre-authorized via PPPC profile |
| System Extension approval | User approves at first run | Pre-approved via profile |
| Binary deployment | `pip install` / clone | Jamf policy or Intune shell script |
| Runs as root at boot | Requires manual LaunchDaemon setup | LaunchDaemon plist via profile or postinstall |
| Silently fails if unsatisfied | Falls back to polling (logged WARNING) | FDA + extension granted before first run |

Without MDM, the agent still works — it falls back to the polling-based telemetry provider
automatically. MDM deployment is required to get native ESF coverage without user
interaction.

---

## 2. Prerequisites

- **Apple Developer ID certificate** in your team keychain, with the
  `com.apple.developer.endpoint-security.client` entitlement provisioned by Apple.
  Request the entitlement from your Apple Developer account at
  [developer.apple.com → Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/identifiers/list).
- **macOS 10.15 (Catalina) or later** on endpoints.
- **MDM solution**: Jamf Pro or Microsoft Intune (both covered below). Any MDM that
  supports Custom Configuration Profiles (`.mobileconfig`) works.
- **SIP must remain enabled**. ESF does _not_ require SIP to be disabled. Disabling SIP
  would actually prevent System Extensions from loading on modern macOS. Verify with
  `csrutil status`.
- **Xcode Command Line Tools** on your build machine (`xcode-select --install`).

---

## 3. Step 1 — Build and sign the ESF helper

### 3.1 Build

```bash
# Default build (host architecture — arm64 on Apple Silicon, x86_64 on Intel)
make -C collector/providers/esf_helper

# Universal binary (runs natively on both Intel and Apple Silicon)
make -C collector/providers/esf_helper universal
```

The output binary is `collector/providers/esf_helper/esf_helper`.

### 3.2 Sign with the ESF entitlement

```bash
codesign \
  --entitlements collector/providers/esf_helper/esf_helper.entitlements \
  --sign "Developer ID Application: <YOUR_COMPANY_NAME> (<YOUR_TEAM_ID>)" \
  --timestamp \
  --options runtime \
  collector/providers/esf_helper/esf_helper
```

Replace `<YOUR_COMPANY_NAME>` and `<YOUR_TEAM_ID>` with your Apple Developer account
values. Your Team ID is a 10-character alphanumeric string visible at
[developer.apple.com → Account → Membership → Team ID](https://developer.apple.com/account).

### 3.3 Verify the signature

```bash
codesign -dv --verbose=4 collector/providers/esf_helper/esf_helper
```

Confirm the output includes:
- `Authority=Developer ID Application: <YOUR_COMPANY_NAME> (<YOUR_TEAM_ID>)`
- `com.apple.developer.endpoint-security.client=1` in the entitlements section

Also check the binary architecture:

```bash
# Should show arm64 (Apple Silicon), x86_64 (Intel), or both (universal)
file collector/providers/esf_helper/esf_helper
lipo -info collector/providers/esf_helper/esf_helper
```

### 3.4 Notarization (required for distribution outside Mac App Store)

```bash
# Zip and submit for notarization
ditto -c -k --keepParent \
  collector/providers/esf_helper/esf_helper \
  esf_helper.zip

xcrun notarytool submit esf_helper.zip \
  --apple-id "<YOUR_APPLE_ID>" \
  --team-id "<YOUR_TEAM_ID>" \
  --password "<YOUR_APP_SPECIFIC_PASSWORD>" \
  --wait
```

Stapling is not applicable to a bare binary (only `.app` bundles and `.pkg` files can
receive a staple); notarization is checked online by Gatekeeper at runtime.

---

## 4. Step 2 — Configure MDM profiles

Two configuration profiles are required. Both use the standard `.mobileconfig` XML
format and can be uploaded directly to Jamf or Intune.

### 4.1 Full Disk Access (PPPC) profile

> **Note**: Replace `<YOUR_TEAM_ID>` with your actual 10-character Apple Team ID
> (visible at developer.apple.com → Membership → Team ID).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.TCC.configuration-profile-policy</string>
            <key>PayloadIdentifier</key>
            <string>com.detec.agent.pppc</string>
            <key>PayloadUUID</key>
            <string>A1B2C3D4-E5F6-7890-ABCD-EF1234567890</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Services</key>
            <dict>
                <key>SystemPolicyAllFiles</key>
                <array>
                    <dict>
                        <key>Allowed</key>
                        <true/>
                        <key>CodeRequirement</key>
                        <string>anchor apple generic and identifier "com.detec.agent" and (certificate leaf[field.1.2.840.113635.100.6.1.13] /* exists */ or certificate 1[field.1.2.840.113635.100.6.2.6] /* exists */ and certificate leaf[field.1.2.840.113635.100.6.1.12] /* exists */ and certificate leaf[subject.OU] = "&lt;YOUR_TEAM_ID&gt;")</string>
                        <key>Comment</key>
                        <string>Detec Agent — Full Disk Access for AI tool scanning</string>
                        <key>Identifier</key>
                        <string>com.detec.agent</string>
                        <key>IdentifierType</key>
                        <string>bundleID</string>
                    </dict>
                </array>
            </dict>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>Grants Full Disk Access to the Detec endpoint agent</string>
    <key>PayloadDisplayName</key>
    <string>Detec Agent — FDA</string>
    <key>PayloadIdentifier</key>
    <string>com.detec.agent.mdm.pppc</string>
    <key>PayloadOrganization</key>
    <string>Your Organization</string>
    <key>PayloadScope</key>
    <string>System</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>B2C3D4E5-F6A7-8901-BCDE-F12345678901</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
```

The `CodeRequirement` value is the standard Developer ID code requirement pattern.
Replace `<YOUR_TEAM_ID>` in the `subject.OU` field with your 10-character Team ID.

### 4.2 System Extension allow-listing profile

This profile pre-approves the `esf_helper` binary as an Endpoint Security Extension,
eliminating the user-facing approval dialog.

> **Note**: Replace `<YOUR_TEAM_ID>` with your 10-character Apple Team ID.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadType</key>
            <string>com.apple.system-extension-policy</string>
            <key>PayloadIdentifier</key>
            <string>com.detec.agent.sysext</string>
            <key>PayloadUUID</key>
            <string>C3D4E5F6-A7B8-9012-CDEF-123456789012</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>AllowedSystemExtensions</key>
            <dict>
                <key>&lt;YOUR_TEAM_ID&gt;</key>
                <array>
                    <string>com.detec.agent.esf-helper</string>
                </array>
            </dict>
            <key>AllowedSystemExtensionTypes</key>
            <dict>
                <key>&lt;YOUR_TEAM_ID&gt;</key>
                <array>
                    <string>EndpointSecurityExtension</string>
                </array>
            </dict>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>Allows the Detec ESF helper as a System Extension</string>
    <key>PayloadDisplayName</key>
    <string>Detec Agent — System Extension</string>
    <key>PayloadIdentifier</key>
    <string>com.detec.agent.mdm.sysext</string>
    <key>PayloadOrganization</key>
    <string>Your Organization</string>
    <key>PayloadScope</key>
    <string>System</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>D4E5F6A7-B8C9-0123-DEF0-234567890123</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
```

---

## 5. Jamf Pro deployment

### 5.1 Package the signed binary

Build a `.pkg` using `pkgbuild`:

```bash
# Create a staging directory
mkdir -p /tmp/detec-stage/usr/local/bin
cp collector/providers/esf_helper/esf_helper /tmp/detec-stage/usr/local/bin/esf_helper
chmod 755 /tmp/detec-stage/usr/local/bin/esf_helper

pkgbuild \
  --root /tmp/detec-stage \
  --identifier com.detec.agent.esf-helper \
  --version 1.0 \
  --install-location / \
  DetecESFHelper.pkg
```

Alternatively, use **Jamf Composer** to create the package from the staged directory.

Sign the package with your Developer ID Installer certificate before uploading:

```bash
productsign \
  --sign "Developer ID Installer: <YOUR_COMPANY_NAME> (<YOUR_TEAM_ID>)" \
  DetecESFHelper.pkg \
  DetecESFHelper-signed.pkg
```

### 5.2 Upload the package to Jamf

1. In Jamf Pro, go to **Settings → Computer Management → Packages**
2. Click **New**, upload `DetecESFHelper-signed.pkg`
3. Set Category and notes as appropriate

### 5.3 Upload the PPPC and System Extension profiles

1. Go to **Computers → Configuration Profiles → New**
2. Set General settings (Name: "Detec Agent — FDA", Level: Computer)
3. Under **Privacy Preferences Policy Control**, upload/paste the PPPC XML from §4.1
4. Repeat for the System Extension profile from §4.2

### 5.4 Create a deployment policy

1. Go to **Computers → Policies → New**
2. Under **Packages**, add the `DetecESFHelper-signed.pkg`
3. Add a **Scripts** step with the post-install LaunchDaemon setup:

```bash
#!/bin/bash
# Post-install: write LaunchDaemon and start the agent
set -e

PLIST="/Library/LaunchDaemons/com.detec.agent.plist"

cat > "$PLIST" <<'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.detec.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/detec-agent</string>
        <string>--daemon</string>
        <string>--api-url</string>
        <string>https://YOUR_DETEC_SERVER/</string>
        <string>--api-key</string>
        <string>YOUR_API_KEY</string>
        <string>--telemetry-provider</string>
        <string>auto</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/detec-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/detec-agent-error.log</string>
</dict>
</plist>
PLIST_EOF

chown root:wheel "$PLIST"
chmod 644 "$PLIST"
launchctl bootstrap system "$PLIST" 2>/dev/null || launchctl load "$PLIST"
```

4. Set the policy trigger to **Recurring Check-in** or **Enrollment Complete**
5. Scope the policy to the target smart group

### 5.5 Order of operations

Deploy the **configuration profiles** (FDA + System Extension) _before_ running the
policy that installs the binary. If the binary launches before FDA is granted, it will
fail with error code 4 and fall back to polling. Profiles take effect within minutes of
MDM check-in; the package deployment policy can be triggered immediately after.

---

## 6. Microsoft Intune deployment

### 6.1 Deploy the binary via Shell Script

1. In Intune, go to **Devices → macOS → Shell Scripts → Add**
2. Use the following script, updating the download URL or embedding the binary as
   base64 if needed:

```bash
#!/bin/bash
# Intune shell script: download and install esf_helper + LaunchDaemon
set -e

BINARY_URL="https://your-internal-distribution/esf_helper"
BINARY_DEST="/usr/local/bin/esf_helper"

curl -fsSL "$BINARY_URL" -o "$BINARY_DEST"
chmod 755 "$BINARY_DEST"

# Install LaunchDaemon (same plist as in §5.4)
PLIST="/Library/LaunchDaemons/com.detec.agent.plist"

cat > "$PLIST" <<'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.detec.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/detec-agent</string>
        <string>--daemon</string>
        <string>--api-url</string>
        <string>https://YOUR_DETEC_SERVER/</string>
        <string>--api-key</string>
        <string>YOUR_API_KEY</string>
        <string>--telemetry-provider</string>
        <string>auto</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/detec-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/detec-agent-error.log</string>
</dict>
</plist>
PLIST_EOF

chown root:wheel "$PLIST"
chmod 644 "$PLIST"
launchctl bootstrap system "$PLIST" 2>/dev/null || launchctl load "$PLIST"
```

3. Set **Run script as signed-in user** to **No** (must run as root)
4. Assign to the target device group

### 6.2 Upload the PPPC and System Extension profiles

1. In Intune, go to **Devices → macOS → Configuration Profiles → Create → New Policy**
2. Select **Profile type: Templates → Custom**
3. Upload the PPPC `.mobileconfig` file from §4.1 as a **Custom macOS Configuration Profile**
4. Repeat for the System Extension profile from §4.2

Microsoft's documentation on custom profiles:
[Create a profile with custom settings in Microsoft Intune](https://learn.microsoft.com/en-us/mem/intune/configuration/custom-settings-macos)

### 6.3 Order of operations

Same as Jamf: push the configuration profiles first, allow MDM check-in to apply them,
then run the shell script that installs and starts the binary.

---

## 7. Verifying the deployment

### 7.1 Check ESF is active on the endpoint

```bash
# Run on the managed endpoint (SSH or Jamf remote command)
detec-agent --dry-run --verbose
```

Look for this line in the output:

```
Using native telemetry provider: ESF
```

If you see `Using telemetry provider: Polling` instead, ESF initialization failed —
see Troubleshooting below.

### 7.2 Check the agent log

```bash
tail -n 50 /var/log/detec-agent.log | grep -i "telemetry\|esf\|provider"
```

A healthy start looks like:

```
INFO  collector.providers.esf_provider — ESF helper started (pid 1234)
INFO  collector.orchestrator — telemetry provider: esf
```

A fallback looks like:

```
WARNING  collector.providers.esf_provider — ESF unavailable (not permitted); falling back to polling
INFO     collector.orchestrator — telemetry provider: polling
```

### 7.3 Check the dashboard

In the Detec dashboard, navigate to **Endpoints** and find the enrolled machine. The
endpoint profile card shows a **Telemetry** badge:

- **Native (ESF)** — ESF is active; real-time event stream is flowing
- **Polling** — ESF is not available; the agent is scanning on the poll interval

---

## 8. Troubleshooting

### Error code 3 — not entitled

```
esf_helper: es_new_client failed: 3
macOS Endpoint Security: not entitled (missing com.apple.developer.endpoint-security.client entitlement)
```

**Cause**: The binary was signed without the ESF entitlement, or with an ad-hoc/development
identity that does not have the entitlement provisioned by Apple.

**Fix**: Re-sign with a Developer ID certificate that has `com.apple.developer.endpoint-security.client`
approved by Apple. Verify the entitlement is present:

```bash
codesign -d --entitlements :- collector/providers/esf_helper/esf_helper | grep endpoint-security
```

### Error code 4 — not permitted (TCC / Full Disk Access)

```
esf_helper: es_new_client failed: 4
macOS Endpoint Security: not permitted (TCC / Full Disk Access or approval required)
```

**Cause**: The PPPC profile was not applied before the agent started, or the profile
code requirement does not match the binary's actual signing identity.

**Fix**:
1. Confirm the profile is installed: `profiles list -all | grep detec`
2. Confirm the code requirement in the profile matches your Team ID:
   `codesign -d --verbose=4 esf_helper 2>&1 | grep "TeamIdentifier"`
3. Re-push the PPPC profile if missing; wait for MDM check-in

### Error code 5 — not privileged

```
esf_helper: es_new_client failed: 5
macOS Endpoint Security: not privileged (Endpoint Security requires root or SIP exception)
```

**Cause**: The agent is not running as root. ESF requires the subscribing process to
have root privileges.

**Fix**: Ensure the LaunchDaemon plist does _not_ have a `<key>UserName</key>` entry
(which would run as that user). LaunchDaemons run as root by default when no `UserName`
is set. Verify:

```bash
launchctl print system/com.detec.agent | grep uid
# Should show: uid = 0
```

### Falls back to polling silently

The agent logs a `WARNING` when ESF is unavailable:

```bash
grep -i "esf\|unavailable\|fallback" /var/log/detec-agent.log
```

Common causes: error codes 3, 4, or 5 above. Also check that `--telemetry-provider` is
`auto` or `native` (not explicitly `polling`).

### Checking error codes manually

```bash
# Run esf_helper directly (as root) to see the raw error
sudo collector/providers/esf_helper/esf_helper /tmp/esf_test.sock
```

---

## 9. Security considerations

### ESF requires root

The `esf_helper` binary runs as root to satisfy macOS's privilege requirement for ESF
clients. This is a macOS platform constraint, not an implementation choice. The trust
boundary is:

- `esf_helper` runs as root, subscribes to ESF events, and emits JSON lines to a
  Unix domain socket
- The main `detec-agent` Python process reads from that socket and processes events
- No event data is written to disk by the helper; the socket is destroyed on disconnect

### Unix domain socket

The helper creates a socket at a path under `/tmp` (e.g. `/tmp/detec_esf_<pid>.sock`)
for IPC with the agent. This socket is local-only (not network-accessible), is unlinked
after the initial `accept()` call, and exists only for the lifetime of the helper
process. See `esf_helper.m` lines 254–315.

### API endpoint isolation

Recommend placing the Detec API server on an internal network segment reachable only
from managed endpoints (not exposed to the public internet). Use TLS with a valid
certificate and configure `--api-url` with an `https://` URL. Set the API key via
environment variable or config file with restricted permissions (`chmod 600`).

### Principle of least privilege for the collector process

If root for the main collector process is not required in your deployment, you can run
`detec-agent` as a non-root user and run `esf_helper` as root via a setuid wrapper or a
dedicated LaunchDaemon entry. However, the simplest and most auditable approach is a
single LaunchDaemon running as root.

### Logging and audit

All ESF-sourced events flow through the standard event pipeline and are visible in the
Detec dashboard. No raw ESF events are persisted on the endpoint beyond the in-memory
event store ring buffer (configurable capacity).
