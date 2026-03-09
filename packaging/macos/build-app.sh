#!/usr/bin/env bash
# Build the Detec Agent macOS .app bundle using PyInstaller.
#
# Prerequisites:
#   pip install pyinstaller
#   pip install -e ".[gui]"   (project with gui extras)
#
# Usage:
#   cd <project-root>
#   bash packaging/macos/build-app.sh
#
# Output:
#   dist/Detec Agent.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Detec Agent macOS Build ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# ---- Step 1: Generate icon assets ----
echo "[1/4] Generating icon assets..."
cd "$PROJECT_ROOT"
python "$SCRIPT_DIR/generate-icons.py"
echo ""

# ---- Step 2: Clean previous build artifacts ----
echo "[2/4] Cleaning previous build..."
rm -rf "$PROJECT_ROOT/build/Detec Agent"
rm -rf "$PROJECT_ROOT/dist/Detec Agent"
rm -rf "$PROJECT_ROOT/dist/Detec Agent.app"
echo "  Done."
echo ""

# ---- Step 3: Run PyInstaller ----
echo "[3/4] Running PyInstaller..."
cd "$PROJECT_ROOT"
pyinstaller "$SCRIPT_DIR/detec-agent.spec" \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build" \
    --noconfirm
echo ""

# ---- Step 4: Verify the .app bundle ----
APP_PATH="$PROJECT_ROOT/dist/Detec Agent.app"
echo "[4/4] Verifying .app bundle..."

if [ ! -d "$APP_PATH" ]; then
    echo "  ERROR: $APP_PATH not found"
    exit 1
fi

echo "  Bundle:     $APP_PATH"
echo "  Executable: $(ls "$APP_PATH/Contents/MacOS/")"
echo "  Info.plist: $(plutil -p "$APP_PATH/Contents/Info.plist" | grep CFBundleVersion)"
echo "  Size:       $(du -sh "$APP_PATH" | cut -f1)"

# Quick sanity check: the binary should exist and be executable
BINARY="$APP_PATH/Contents/MacOS/detec-agent-gui"
if [ -x "$BINARY" ]; then
    echo "  Binary OK:  executable"
else
    echo "  WARNING: binary not found or not executable at $BINARY"
fi

echo ""
echo "=== Build complete ==="
echo "To test: open \"$APP_PATH\""
echo "To sign: codesign --deep --force --sign \"Developer ID Application: <TEAM>\" \"$APP_PATH\""
