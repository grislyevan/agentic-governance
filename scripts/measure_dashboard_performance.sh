#!/usr/bin/env bash
# Measure dashboard build time and bundle size for performance baseline.
# Run from repo root: bash scripts/measure_dashboard_performance.sh
# See docs/dashboard-performance.md.

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/dashboard"

echo "Dashboard performance (build time and bundle size)"
echo "  Working directory: $(pwd)"

# Build and time
start=$SECONDS
npm run build --silent
elapsed=$((SECONDS - start))
echo "  Build time: ${elapsed}s"

# Bundle size (dist/)
if [ -d dist ]; then
  size=$(du -sh dist 2>/dev/null | cut -f1)
  echo "  dist/ size: $size"
  echo "  JS chunks:"
  find dist -name "*.js" -exec du -h {} \; 2>/dev/null | sort -hr | head -5
else
  echo "  dist/ not found"
fi

echo ""
echo "For load time and LCP, run Lighthouse against the served app:"
echo "  npm run build && npm run preview  # then npx lighthouse http://localhost:4173 --view"
