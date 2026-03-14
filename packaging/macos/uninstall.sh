#!/usr/bin/env bash
# Uninstall the Detec Agent from macOS.
#
# Removes the app, LaunchAgent, config, logs, state, Keychain entry,
# and the installer receipt. Run with sudo for a clean removal.
#
# Tamper controls: Uninstall must be run as root/sudo so that all
# components (including LaunchAgent and system paths) can be removed.
# If the agent is installed as a LaunchDaemon (Phase 1.1.3), only root
# can unload it; this script or a daemon-specific path must be run with
# sudo. See docs/tamper-controls.md.
#
# Usage:
#   sudo bash packaging/macos/uninstall.sh
#
# Or from anywhere:
#   sudo bash /path/to/uninstall.sh

set -euo pipefail

PLIST_LABEL="com.detec.agent"
APP_PATH="/Applications/Detec Agent.app"
LAUNCH_DAEMON_PLIST="/Library/LaunchDaemons/$PLIST_LABEL.plist"

# Tamper control: if LaunchDaemon is installed, only root can unload it. Require root now.
if [ -f "$LAUNCH_DAEMON_PLIST" ] && [ "$(id -u)" -ne 0 ]; then
    echo "Error: LaunchDaemon is installed. Uninstall must be run as root (e.g. sudo). See docs/tamper-controls.md."
    exit 1
fi

# Resolve the real user (the script may run as root via sudo).
if [ -n "${SUDO_USER:-}" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_USER="$(whoami)"
    REAL_HOME="$HOME"
fi

LAUNCH_AGENT_PLIST="$REAL_HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_DIR="$REAL_HOME/Library/Logs/DetecAgent"
STATE_DIR="$REAL_HOME/.agentic-gov"
APP_SUPPORT_DIR="$REAL_HOME/Library/Application Support/Detec"
SYSTEM_APP_SUPPORT="/Library/Application Support/Detec"
SYSTEM_LOG_DIR="/Library/Logs/DetecAgent"

echo ""
echo "=== Detec Agent Uninstaller ==="
echo ""
echo "This will remove:"
echo "  App:          $APP_PATH"
echo "  LaunchDaemon: $LAUNCH_DAEMON_PLIST"
echo "  LaunchAgent:  $LAUNCH_AGENT_PLIST (if present)"
echo "  Config:       $APP_SUPPORT_DIR, $SYSTEM_APP_SUPPORT"
echo "  Logs:         $LOG_DIR, $SYSTEM_LOG_DIR"
echo "  State:        $STATE_DIR"
echo "  Keychain:     detec-agent (if present)"
echo "  Receipt:      $PLIST_LABEL"
echo ""

# ---- Step 1: Stop and unload LaunchDaemon and LaunchAgent ----
echo "[1/6] Stopping the agent..."

if [ -f "$LAUNCH_DAEMON_PLIST" ]; then
    launchctl bootout "system/$PLIST_LABEL" 2>/dev/null || true
    launchctl unload "$LAUNCH_DAEMON_PLIST" 2>/dev/null || true
    echo "  LaunchDaemon unloaded."
fi

REAL_UID="$(id -u "$REAL_USER")"
if launchctl print "gui/$REAL_UID/$PLIST_LABEL" &>/dev/null; then
    launchctl bootout "gui/$REAL_UID/$PLIST_LABEL" 2>/dev/null || true
    echo "  LaunchAgent unloaded."
elif [ -f "$LAUNCH_AGENT_PLIST" ]; then
    sudo -u "$REAL_USER" launchctl unload "$LAUNCH_AGENT_PLIST" 2>/dev/null || true
fi

# Kill any remaining processes
pkill -f "Detec Agent" 2>/dev/null || true
pkill -f "detec-agent-gui" 2>/dev/null || true
sleep 1

# ---- Step 2: Remove LaunchDaemon and LaunchAgent plists ----
echo "[2/6] Removing LaunchDaemon and LaunchAgent plists..."
if [ -f "$LAUNCH_DAEMON_PLIST" ]; then
    rm -f "$LAUNCH_DAEMON_PLIST"
    echo "  Removed $LAUNCH_DAEMON_PLIST"
fi
if [ -f "$LAUNCH_AGENT_PLIST" ]; then
    rm -f "$LAUNCH_AGENT_PLIST"
    echo "  Removed $LAUNCH_AGENT_PLIST"
fi

# ---- Step 3: Remove the application ----
echo "[3/6] Removing application..."
if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    echo "  Removed $APP_PATH"
else
    echo "  Not found (already removed)."
fi

# ---- Step 4: Remove config, logs, and state ----
echo "[4/6] Removing config, logs, and state..."

for dir in "$APP_SUPPORT_DIR" "$LOG_DIR" "$STATE_DIR" "$SYSTEM_APP_SUPPORT" "$SYSTEM_LOG_DIR"; do
    if [ -d "$dir" ]; then
        rm -rf "$dir"
        echo "  Removed $dir"
    fi
done

# ---- Step 5: Remove Keychain entry ----
echo "[5/6] Removing Keychain entry..."
if sudo -u "$REAL_USER" security find-generic-password -s "detec-agent" &>/dev/null; then
    sudo -u "$REAL_USER" security delete-generic-password -s "detec-agent" &>/dev/null || true
    echo "  Removed Keychain entry for detec-agent."
else
    echo "  No Keychain entry found."
fi

# ---- Step 6: Forget the installer receipt ----
echo "[6/6] Removing installer receipt..."
if pkgutil --pkg-info "$PLIST_LABEL" &>/dev/null; then
    pkgutil --forget "$PLIST_LABEL" &>/dev/null || true
    echo "  Forgot package receipt $PLIST_LABEL"
else
    echo "  No installer receipt found."
fi

echo ""
echo "=== Detec Agent has been completely removed ==="
echo ""
