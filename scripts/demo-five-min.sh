#!/usr/bin/env bash
# Five-minute demo: start API + dashboard with demo data.
# Run from repo root. See docs/demo.md for full instructions.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Detec five-minute demo ==="
echo "Repo root: $REPO_ROOT"
echo ""

# Prechecks
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 not found. Install Python 3.10+ and try again."
  exit 1
fi
if ! command -v node &>/dev/null; then
  echo "Error: node not found. Install Node 18+ and try again."
  exit 1
fi

# Optional: ensure package and dashboard deps (skip if user already has them)
if ! python3 -c "import collector" 2>/dev/null; then
  echo "Installing Detec package (pip install -e .)..."
  pip install -e . -q
fi
if [[ ! -d "$REPO_ROOT/dashboard/node_modules" ]]; then
  echo "Installing dashboard dependencies..."
  (cd "$REPO_ROOT/dashboard" && npm install --silent)
fi

# Build dashboard
echo "Building dashboard..."
(cd "$REPO_ROOT/dashboard" && npm run build)

# Env for demo: demo mode, JWT secret, seed admin password
export DEMO_MODE=true
export JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32 2>/dev/null || echo 'demo-secret-change-me')}"
export SEED_ADMIN_PASSWORD="${SEED_ADMIN_PASSWORD:-change-me}"
export SEED_ADMIN_EMAIL="${SEED_ADMIN_EMAIL:-admin@example.com}"

echo ""
echo "Starting API with demo mode (DEMO_MODE=true)."
echo "On first run, seed creates a default tenant and demo data automatically."
echo ""

# Run API from api/ so uvicorn finds main:app
(
  cd "$REPO_ROOT/api"
  if [[ -f .env ]]; then
    set -a
    source .env
    set +a
  fi
  export DEMO_MODE=true
  export JWT_SECRET="${JWT_SECRET}"
  export SEED_ADMIN_PASSWORD="${SEED_ADMIN_PASSWORD}"
  export SEED_ADMIN_EMAIL="${SEED_ADMIN_EMAIL}"
  exec uvicorn main:app --host 0.0.0.0 --port 8000
) &
API_PID=$!
trap "kill $API_PID 2>/dev/null || true" EXIT

# Wait for API to be up
echo "Waiting for API to be ready..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null | grep -q 200; then
    break
  fi
  sleep 0.5
done
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null | grep -q 200; then
  echo "API did not become ready in time. Check logs above."
  exit 1
fi

echo ""
echo "----------------------------------------------------------------------"
echo "  Dashboard:  http://localhost:8000"
echo "  Login:      $SEED_ADMIN_EMAIL / $SEED_ADMIN_PASSWORD"
echo "----------------------------------------------------------------------"
echo ""
echo "Open the URL above and log in to see demo endpoints, events, and policy decisions."
echo "To reset demo data after logging in: POST /api/demo/reset (owner only)."
echo "Press Ctrl+C to stop the API."
echo ""

# Optional: open browser (macOS)
if [[ "$(uname)" == "Darwin" ]] && command -v open &>/dev/null; then
  sleep 1
  open "http://localhost:8000" 2>/dev/null || true
fi

wait $API_PID
