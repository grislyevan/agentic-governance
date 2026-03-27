#!/usr/bin/env bash
set -euo pipefail

DASHBOARD_DIR="$(cd "$(dirname "$0")/../../dashboard" && pwd)"
OUTPUT_DIR="${1:-/tmp/lighthouse-results}"
mkdir -p "$OUTPUT_DIR"

echo "Building dashboard..."
cd "$DASHBOARD_DIR"
npm run build

echo "Starting preview server..."
npx vite preview --port 4173 &
PREVIEW_PID=$!
trap "kill $PREVIEW_PID 2>/dev/null || true" EXIT

# Wait for server to be ready
timeout=30
elapsed=0
until curl --silent --fail --output /dev/null http://localhost:4173/; do
  if [ "$elapsed" -ge "$timeout" ]; then
    echo "ERROR: Preview server did not become ready within ${timeout}s"
    exit 1
  fi
  echo "  Waiting for preview server... (${elapsed}s/${timeout}s)"
  sleep 2
  elapsed=$((elapsed + 2))
done
echo "  Preview server is ready (took ~${elapsed}s)"

echo "Running Lighthouse on core views..."
for ROUTE in "" "events" "sessions" "approvals" "exceptions"; do
  URL="http://localhost:4173/${ROUTE}"
  SLUG="${ROUTE:-dashboard}"
  echo "  Measuring $URL..."
  npx lighthouse "$URL" \
    --output json \
    --output-path "$OUTPUT_DIR/lighthouse-${SLUG}.json" \
    --chrome-flags="--headless --no-sandbox" \
    --quiet || echo "  WARNING: Lighthouse failed for $SLUG"
done

echo "Extracting key metrics..."
for RESULT_FILE in "$OUTPUT_DIR"/lighthouse-*.json; do
  SLUG=$(basename "$RESULT_FILE" .json | sed 's/lighthouse-//')
  if [ -f "$RESULT_FILE" ]; then
    SCORE=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d['categories']['performance']['score'])" 2>/dev/null || echo "N/A")
    FCP=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d['audits']['first-contentful-paint']['displayValue'])" 2>/dev/null || echo "N/A")
    LCP=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d['audits']['largest-contentful-paint']['displayValue'])" 2>/dev/null || echo "N/A")
    echo "  $SLUG: score=$SCORE FCP=$FCP LCP=$LCP"
  fi
done

echo "Results saved to $OUTPUT_DIR"
