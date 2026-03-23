#!/usr/bin/env bash
# Build + install Detec Windows agent from macOS in one shot.
#
# Usage:
#   WINDOWS_HOST=evan@192.168.0.72 WINDOWS_PASSWORD='secret' ./scripts/setup-windows-agent-from-mac.sh
#
# Optional env vars:
#   SERVER_API_URL   (default: http://localhost:8000/api)
#   AGENT_API_URL    (default: http://<this-mac-lan-ip>:8000/api)
#   ADMIN_EMAIL      (default: read from api/.env or .env)
#   ADMIN_PASSWORD   (default: read from api/.env or .env)
#   WINDOWS_SRC_DIR  (default: C:/src)

set -euo pipefail

WINDOWS_HOST="${WINDOWS_HOST:-evan@192.168.0.72}"
WINDOWS_PASSWORD="${WINDOWS_PASSWORD:-}"
SERVER_API_URL="${SERVER_API_URL:-http://localhost:8000/api}"
WINDOWS_SRC_DIR="${WINDOWS_SRC_DIR:-C:/src}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"
REPO_PARENT="$(dirname "$REPO_ROOT")"

if [ -z "${AGENT_API_URL:-}" ]; then
  MAC_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
  AGENT_API_URL="${MAC_IP:+http://$MAC_IP:8000/api}"
fi
AGENT_API_URL="${AGENT_API_URL:-http://192.168.0.54:8000/api}"

for f in "$REPO_ROOT/api/.env" "$REPO_ROOT/.env"; do
  if [ -f "$f" ]; then
    [ -z "${ADMIN_EMAIL:-}" ] && ADMIN_EMAIL=$(grep -E "^SEED_ADMIN_EMAIL=" "$f" 2>/dev/null | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]$//")
    [ -z "${ADMIN_PASSWORD:-}" ] && ADMIN_PASSWORD=$(grep -E "^SEED_ADMIN_PASSWORD=" "$f" 2>/dev/null | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]$//")
  fi
done
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-change-me}"

SSH_OPTS=(-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

ssh_cmd() {
  if [ -n "$WINDOWS_PASSWORD" ]; then
    command -v sshpass >/dev/null || { echo "ERROR: WINDOWS_PASSWORD set but sshpass not installed"; exit 1; }
    sshpass -p "$WINDOWS_PASSWORD" ssh "${SSH_OPTS[@]}" "$@"
  else
    ssh "${SSH_OPTS[@]}" "$@"
  fi
}

scp_cmd() {
  if [ -n "$WINDOWS_PASSWORD" ]; then
    command -v sshpass >/dev/null || { echo "ERROR: WINDOWS_PASSWORD set but sshpass not installed"; exit 1; }
    sshpass -p "$WINDOWS_PASSWORD" scp "${SSH_OPTS[@]}" "$@"
  else
    scp "${SSH_OPTS[@]}" "$@"
  fi
}

echo "=== Detec Windows one-shot setup ==="
echo "  Windows:       $WINDOWS_HOST"
echo "  Server (curl): $SERVER_API_URL"
echo "  Agent API:     $AGENT_API_URL"

echo "[1/6] Getting tenant agent key..."
LOGIN_RESP=$(curl -s -w "\n%{http_code}" -X POST "$SERVER_API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")
HTTP_CODE=$(echo "$LOGIN_RESP" | tail -n1)
LOGIN_BODY=$(echo "$LOGIN_RESP" | sed '$d')
ACCESS_TOKEN=$(echo "$LOGIN_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)
if [ -z "$ACCESS_TOKEN" ]; then
  echo "ERROR: Login failed (HTTP $HTTP_CODE)"
  echo "$LOGIN_BODY"
  exit 1
fi
ROTATE_RESP=$(curl -s -X POST "$SERVER_API_URL/agent/key/rotate" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json")
AGENT_KEY=$(echo "$ROTATE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('agent_key',''))" 2>/dev/null)
if [ -z "$AGENT_KEY" ]; then
  echo "ERROR: Failed to rotate/get agent key"
  echo "$ROTATE_RESP"
  exit 1
fi
echo "  Agent key prefix: ${AGENT_KEY:0:8}..."

echo "[2/6] Packaging repo for Windows build..."
TARBALL=$(mktemp /tmp/detec-win-src.XXXXXX.tar.gz)
BUILD_PS1=$(mktemp /tmp/detec-win-build.XXXXXX.ps1)
trap 'rm -f "$TARBALL" "$BUILD_PS1"' EXIT

(
  cd "$REPO_PARENT"
  tar -czf "$TARBALL" \
    --exclude="$REPO_NAME/.git" \
    --exclude="$REPO_NAME/node_modules" \
    --exclude="$REPO_NAME/.claude" \
    --exclude="$REPO_NAME/.cursor" \
    --exclude="$REPO_NAME/.pytest_cache" \
    --exclude="$REPO_NAME/.mypy_cache" \
    --exclude="$REPO_NAME/.venv" \
    --exclude="$REPO_NAME/venv" \
    --exclude="$REPO_NAME/dashboard/dist" \
    --exclude="$REPO_NAME/api/dist" \
    --exclude="$REPO_NAME/packaging/macos/dist" \
    --exclude='*.app' \
    --exclude='*.pyc' \
    "$REPO_NAME"
)

echo "[3/6] Copying source to Windows..."
ssh_cmd "$WINDOWS_HOST" "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path $WINDOWS_SRC_DIR | Out-Null; if (Test-Path '$WINDOWS_SRC_DIR/$REPO_NAME') { Remove-Item -Recurse -Force '$WINDOWS_SRC_DIR/$REPO_NAME' }\""
scp_cmd "$TARBALL" "$WINDOWS_HOST:$WINDOWS_SRC_DIR/$REPO_NAME.tar.gz"
ssh_cmd "$WINDOWS_HOST" "powershell -NoProfile -ExecutionPolicy Bypass -Command \"tar -xzf '$WINDOWS_SRC_DIR/$REPO_NAME.tar.gz' -C '$WINDOWS_SRC_DIR'\""

cat > "$BUILD_PS1" <<PS1
\$ErrorActionPreference='Stop'
\$repo='$WINDOWS_SRC_DIR/$REPO_NAME'
\$py='C:\\Program Files\\Python311\\python.exe'

if (!(Test-Path \$repo)) { throw "Repo missing at \$repo" }

# Ensure Python 3.11 exists
if (!(Test-Path \$py)) {
  Write-Host 'Python 3.11 not found. Installing...'
  \$installer='$WINDOWS_SRC_DIR/python-3.11.9-amd64.exe'
  Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile \$installer
  Start-Process -FilePath \$installer -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait
  if (!(Test-Path \$py)) { throw 'Python install failed' }
}

Set-Location \$repo
& \$py -m pip install --upgrade pip
& \$py -m pip install -e .
& \$py -m pip install pyinstaller pywin32

Set-Location "\$repo\\installers\\windows"
& \$py -m PyInstaller --clean --noconfirm detec-agent.spec

\$exe="\$repo\\installers\\windows\\dist\\detec-agent\\detec-agent.exe"
if (!(Test-Path \$exe)) { throw 'detec-agent.exe build failed' }

# Configure agent and install service
& \$exe setup --api-url "$AGENT_API_URL" --api-key "$AGENT_KEY" --interval 60 --protocol auto --force
& \$exe install-service
sc.exe config DetecAgent start= auto | Out-Null

Write-Host "\n=== Final status ==="
& \$exe status
Get-Service -Name DetecAgent | Select-Object Name,Status,StartType
PS1

echo "[4/6] Uploading build script..."
scp_cmd "$BUILD_PS1" "$WINDOWS_HOST:$WINDOWS_SRC_DIR/build-detec-agent.ps1"

echo "[5/6] Building EXE + installing service on Windows (this can take a few minutes)..."
ssh_cmd "$WINDOWS_HOST" "powershell -NoProfile -ExecutionPolicy Bypass -File $WINDOWS_SRC_DIR/build-detec-agent.ps1"

echo "[6/6] Done."
echo "  EXE:      $WINDOWS_SRC_DIR/$REPO_NAME/installers/windows/dist/detec-agent/detec-agent.exe"
echo "  Service:  DetecAgent (auto-start)"
echo "  API URL:  $AGENT_API_URL"
echo

echo "Tip: rotate any password shared in chat after lab work."
