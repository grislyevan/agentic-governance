# Dashboard Performance Benchmarks

**Workstream 4 (Task 4.2).** Measurable criteria for the Detec SOC dashboard: build time, bundle size, and (when served) load time. Use for regression and baseline documentation.

## Build time and bundle size

- **Script:** [scripts/measure_dashboard_performance.sh](../scripts/measure_dashboard_performance.sh) runs `npm run build` in the dashboard, reports build time (seconds) and `dist/` size, and lists the largest JS chunks.
- **Usage (from repo root):** `bash scripts/measure_dashboard_performance.sh`. Requires Node and npm; run after `npm ci` or `npm install` in `dashboard/`.
- **Baseline:** Run on a representative machine and record results. Example placeholder: "Build time: 12s; dist/ size: 2.1M; largest chunk: index-xxx.js 1.2M." Replace with actual numbers.

## Load time and LCP (when app is served)

- **Method:** Serve the built dashboard (e.g. `npm run preview` in dashboard, or FastAPI serving the built static files) and run Lighthouse: `npx lighthouse http://localhost:4173 --only-categories=performance --output=json --output-path=./lighthouse-report.json --chrome-flags="--headless"`. Open the report for Performance score, LCP, FCP.
- **Heavy views:** Dashboard home (endpoints list), Events list with many items, and endpoint detail are the main views to measure. Use Lighthouse or DevTools Performance to record load time for list view with many endpoints (e.g. 100+).
- **Baseline:** Document "Dashboard home load (LCP): Xs; Events list (100 items): Xs" when you have a run. Optional: add a CI job that runs Lighthouse in headless mode and fails if Performance score drops below a threshold.

## Summary

- **In-repo repeatable:** Build time and bundle size via `scripts/measure_dashboard_performance.sh`.
- **Requires served app:** Load time and LCP via Lighthouse against running server; document baseline in this file or in SECURITY-TECHNICAL-REPORT.
