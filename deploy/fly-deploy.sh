#!/usr/bin/env bash
# Deploy Detec API to Fly.io
#
# Prerequisites:
#   - flyctl installed (curl -L https://fly.io/install.sh | sh)
#   - Authenticated (fly auth login)
#   - Node.js installed (for dashboard build)
#
# Usage:
#   ./deploy/fly-deploy.sh              # Full deploy (build dashboard + deploy)
#   ./deploy/fly-deploy.sh --skip-build # Deploy only (dashboard/dist must exist)
#   ./deploy/fly-deploy.sh --setup      # First-time setup (create app + database + secrets)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="detec-api"
DB_NAME="detec-db"

# ── Parse args ────────────────────────────────────────────────────────

SKIP_BUILD=false
SETUP=false

for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --setup)      SETUP=true ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

# ── Preflight ─────────────────────────────────────────────────────────

if ! command -v fly &>/dev/null && ! command -v flyctl &>/dev/null; then
    echo "Error: flyctl not installed."
    echo "Install: curl -L https://fly.io/install.sh | sh"
    exit 1
fi

FLY="$(command -v flyctl 2>/dev/null || command -v fly)"

cd "$REPO_ROOT"

# ── First-time setup ─────────────────────────────────────────────────

if [ "$SETUP" = true ]; then
    echo "==> First-time setup for $APP_NAME"

    echo "--- Creating app (if needed)..."
    $FLY apps create "$APP_NAME" --org personal 2>/dev/null || echo "App may already exist, continuing."

    echo "--- Creating Postgres database..."
    $FLY postgres create --name "$DB_NAME" --region sjc --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1 || echo "DB may already exist."

    echo "--- Attaching database to app..."
    $FLY postgres attach "$DB_NAME" --app "$APP_NAME" || echo "Already attached."

    echo "--- Setting secrets..."
    JWT_SECRET="$(openssl rand -hex 32)"
    read -rp "Admin password for seed user: " ADMIN_PW
    read -rp "Allowed origins (e.g. https://detec-api.fly.dev): " ORIGINS

    $FLY secrets set \
        JWT_SECRET="$JWT_SECRET" \
        SEED_ADMIN_PASSWORD="$ADMIN_PW" \
        ALLOWED_ORIGINS="$ORIGINS" \
        DEMO_MODE="true" \
        --app "$APP_NAME"

    echo ""
    echo "==> Setup complete. Now run: ./deploy/fly-deploy.sh"
    exit 0
fi

# ── Build dashboard ──────────────────────────────────────────────────

if [ "$SKIP_BUILD" = false ]; then
    echo "==> Building dashboard..."
    cd dashboard
    npm ci
    npm run build
    cd "$REPO_ROOT"
fi

if [ ! -d "dashboard/dist" ]; then
    echo "Error: dashboard/dist not found. Run without --skip-build first."
    exit 1
fi

# ── Deploy ───────────────────────────────────────────────────────────

echo "==> Deploying to Fly.io..."
$FLY deploy --app "$APP_NAME"

echo ""
echo "==> Deploy complete. Checking health..."
sleep 10

$FLY status --app "$APP_NAME"

echo ""
echo "--- Health check:"
curl -sf "https://$APP_NAME.fly.dev/api/health" | python3 -m json.tool 2>/dev/null || echo "Health check pending (may take a moment to start)."

echo ""
echo "==> Dashboard: https://$APP_NAME.fly.dev"
echo "==> API:       https://$APP_NAME.fly.dev/api"
echo "==> Health:    https://$APP_NAME.fly.dev/api/health"
