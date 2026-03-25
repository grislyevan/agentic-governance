# Dashboard Performance Benchmarks

**Workstream 4 (Task 4.2).** Measurable criteria for the Detec SOC dashboard: build time, bundle size, and (when served) load time. Use for regression and baseline documentation.

## Build time and bundle size

- **Script:** [scripts/measure_dashboard_performance.sh](../scripts/measure_dashboard_performance.sh) runs `npm run build` in the dashboard, reports build time (seconds) and `dist/` size, and lists the largest JS chunks.
- **Usage (from repo root):** `bash scripts/measure_dashboard_performance.sh`. Requires Node and npm; run after `npm ci` or `npm install` in `dashboard/`.
- **Baseline:** Baseline (2026-03-24, macOS ARM64, Node 20): Build time: 3s; dist/ size: 976K; largest chunks: index-Dkd2yNEe.js 484K (484.04 kB raw / 122.82 kB gzip), index-DDPs6xYr.css 48K (47.93 kB raw / 8.88 kB gzip), index.html 1.08 kB.
- Re-run `bash scripts/measure_dashboard_performance.sh` after significant UI changes to detect regressions.

## Load time and LCP (when app is served)

- **Method:** Serve the built dashboard (e.g. `npm run preview` in dashboard, or FastAPI serving the built static files) and run Lighthouse: `npx lighthouse http://localhost:4173 --only-categories=performance --output=json --output-path=./lighthouse-report.json --chrome-flags="--headless"`. Open the report for Performance score, LCP, FCP.
- **Heavy views:** Dashboard home (endpoints list), Events list with many items, and endpoint detail are the main views to measure. Use Lighthouse or DevTools Performance to record load time for list view with many endpoints (e.g. 100+).
- **Baseline:** Document "Dashboard home load (LCP): Xs; Events list (100 items): Xs" when you have a run. Optional: add a CI job that runs Lighthouse in headless mode and fails if Performance score drops below a threshold. Baseline: not yet recorded. Record when serving against representative data set.

## Summary

- **In-repo repeatable:** Build time and bundle size via `scripts/measure_dashboard_performance.sh`.
- **Requires served app:** Load time and LCP via Lighthouse against running server; document baseline in this file or in SECURITY-TECHNICAL-REPORT.

## Lighthouse Baseline

> **Note:** Baseline captured via `scripts/lighthouse/run.sh` in CI (headless Chrome). Run locally with `bash scripts/lighthouse/run.sh /tmp/lh-results` to update.
>
> *Initial capture pending first CI run. Values below are thresholds; actual measurements will replace these after the first successful CI run.*

| View        | Score  | FCP    | LCP    |
|-------------|--------|--------|--------|
| /dashboard  | TBD    | TBD    | TBD    |
| /events     | TBD    | TBD    | TBD    |
| /sessions   | TBD    | TBD    | TBD    |
| /approvals  | TBD    | TBD    | TBD    |
| /exceptions | TBD    | TBD    | TBD    |

## Budget Thresholds

| Metric          | Soft (warn) | Hard (fail CI) |
|-----------------|-------------|----------------|
| Performance     | < 0.70      | < 0.50         |
| LCP             | > 3.5 s     | > 5.0 s        |
| FCP             | > 2.0 s     | > 3.5 s        |
| Bundle chunk    | > 600 KB    | > 700 KB       |
