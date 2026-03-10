#!/usr/bin/env bash
# Build a macOS .pkg installer for the Detec Agent.
#
# Prerequisites:
#   - The .app bundle must already exist at dist/Detec Agent.app
#     (run build-app.sh first)
#   - macOS developer tools (pkgbuild, productbuild are built-in)
#
# Usage:
#   cd <project-root>
#   bash packaging/macos/build-pkg.sh
#
# Output:
#   dist/DetecAgent-<version>.pkg
#
# For signed packages, set SIGNING_IDENTITY:
#   SIGNING_IDENTITY="Developer ID Installer: Your Name (TEAMID)" \
#       bash packaging/macos/build-pkg.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Extract version from pyproject.toml
VERSION=$(python3 -c "
import re
text = open('$PROJECT_ROOT/pyproject.toml').read()
m = re.search(r'version\s*=\s*\"([^\"]+)\"', text)
print(m.group(1) if m else '0.3.0')
")

APP_PATH="$PROJECT_ROOT/dist/Detec Agent.app"
PKG_DIR="$PROJECT_ROOT/dist/pkg-staging"
COMPONENT_PKG="$PKG_DIR/DetecAgent.pkg"
FINAL_PKG="$PROJECT_ROOT/dist/DetecAgent-${VERSION}.pkg"

echo "=== Detec Agent .pkg Installer Build ==="
echo "Version:      $VERSION"
echo "App bundle:   $APP_PATH"
echo ""

# ---- Verify .app exists ----
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH not found."
    echo "Run build-app.sh first to create the .app bundle."
    exit 1
fi

# ---- Optional: bake in server config ----
# When API_URL and API_KEY are set, write agent.env into the .app bundle
# so the postinstall script can copy it to ~/Library/Application Support/Detec/.
if [ -n "${API_URL:-}" ] && [ -n "${API_KEY:-}" ]; then
    BAKED_CONFIG_DIR="$APP_PATH/Contents/Resources/config"
    mkdir -p "$BAKED_CONFIG_DIR"
    cat > "$BAKED_CONFIG_DIR/agent.env" << AGENTENV
AGENTIC_GOV_API_URL=${API_URL}
AGENTIC_GOV_API_KEY=${API_KEY}
AGENTIC_GOV_INTERVAL=${AGENT_INTERVAL:-300}
AGENTIC_GOV_PROTOCOL=${AGENT_PROTOCOL:-http}
AGENTENV
    echo "  Baked server config into $BAKED_CONFIG_DIR/agent.env"
else
    echo "  No API_URL/API_KEY set; building generic package (manual setup required)."
fi

# ---- Clean staging area ----
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"

# ---- Step 1: Build the component package ----
echo "[1/3] Building component package..."

pkgbuild \
    --root "$APP_PATH" \
    --install-location "/Applications/Detec Agent.app" \
    --identifier "com.detec.agent" \
    --version "$VERSION" \
    --scripts "$SCRIPT_DIR/scripts" \
    "$COMPONENT_PKG"

echo "  Component package: $COMPONENT_PKG"
echo ""

# ---- Step 2: Build the distribution package ----
echo "[2/3] Building distribution package..."

SIGN_FLAGS=""
if [ -n "${SIGNING_IDENTITY:-}" ]; then
    SIGN_FLAGS="--sign \"$SIGNING_IDENTITY\""
    echo "  Signing with: $SIGNING_IDENTITY"
fi

# Copy resources alongside the distribution.xml
cp "$SCRIPT_DIR/resources/welcome.html" "$PKG_DIR/welcome.html"
cp "$SCRIPT_DIR/resources/readme.html" "$PKG_DIR/readme.html"

eval productbuild \
    --distribution "$SCRIPT_DIR/distribution.xml" \
    --resources "$PKG_DIR" \
    --package-path "$PKG_DIR" \
    $SIGN_FLAGS \
    "$FINAL_PKG"

echo "  Distribution package: $FINAL_PKG"
echo ""

# ---- Step 3: Verify ----
echo "[3/3] Verifying package..."
echo "  Size: $(du -sh "$FINAL_PKG" | cut -f1)"

# Check if signed
if pkgutil --check-signature "$FINAL_PKG" 2>/dev/null | grep -q "signed"; then
    echo "  Signature: Valid"
else
    echo "  Signature: Unsigned (set SIGNING_IDENTITY to sign)"
fi

# Clean staging
rm -rf "$PKG_DIR"

echo ""
echo "=== Package build complete ==="
echo "Installer: $FINAL_PKG"
echo ""
echo "To install locally:  sudo installer -pkg \"$FINAL_PKG\" -target /"
echo "To deploy via MDM:   Upload $FINAL_PKG to Jamf Pro or Endpoint Central"
