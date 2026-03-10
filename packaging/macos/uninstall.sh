#!/usr/bin/env bash
# Uninstall the Detec Agent from macOS.
#
# Removes the app, LaunchAgent, config, logs, state, Keychain entry,
# and the installer receipt. Run with sudo for a clean removal.
#
# Usage:
#   sudo bash packaging/macos/uninstall.sh
#
# Or from anywhere:
#   sudo bash /path/to/uninstall.sh

set -euo pipefail

PLIST_LABEL="com.detec.agent"
APP_PATH="/Applications/Detec Agent.app"

# Resolve the real user (the script may run as root via sudo).
if [ -n "${SUDO_USER:-}" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_USER="$(whoami)"
    REAL_HOME="$HOME"
fi

PLIST_PATH="$REAL_HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_DIR="$REAL_HOME/Library/Logs/DetecAgent"
STATE_DIR="$REAL_HOME/.agentic-gov"
APP_SUPPORT_DIR="$REAL_HOME/Library/Application Support/Detec"

echo ""
echo "=== Detec Agent Uninstaller ==="
echo ""
echo "This will remove:"
echo "  App:        $APP_PATH"
echo "  LaunchAgent: $PLIST_PATH"
echo "  Config:     $APP_SUPPORT_DIR"
echo "  Logs:       $LOG_DIR"
echo "  State:      $STATE_DIR"
echo "  Keychain:   detec-agent (if present)"
echo "  Receipt:    $PLIST_LABEL"
echo ""

# ---- Step 1: Stop and unload the LaunchAgent ----
echo "[1/6] Stopping the agent..."

REAL_UID="$(id -u "$REAL_USER")"
if launchctl print "gui/$REAL_UID/$PLIST_LABEL" &>/dev/null; then
    launchctl bootout "gui/$REAL_UID/$PLIST_LABEL" 2>/dev/null || true
    echo "  LaunchAgent unloaded."
else
    # Fallback for older macOS
    sudo -u "$REAL_USER" launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo "  LaunchAgent was not loaded (or already stopped)."
fi

# Kill any remaining processes
pkill -f "Detec Agent" 2>/dev/null || true
pkill -f "detec-agent-gui" 2>/dev/null || true
sleep 1

# ---- Step 2: Remove the LaunchAgent plist ----
echo "[2/6] Removing LaunchAgent..."
if [ -f "$PLIST_PATH" ]; then
    rm -f "$PLIST_PATH"
    echo "  Removed $PLIST_PATH"
else
    echo "  Not found (already removed)."
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

for dir in "$APP_SUPPORT_DIR" "$LOG_DIR" "$STATE_DIR"; do
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
