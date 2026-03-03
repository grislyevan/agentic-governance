# Agentic Governance Dashboard

Minimal web UI for the agentic-governance collector: single-endpoint view of detected AI tools, confidence, and policy decisions.

## Quick start

1. **Produce NDJSON** (from repo root):
   ```bash
   cd collector && python main.py
   ```
   This writes to `collector/scan-results.ndjson`. To print to stdout instead: `python main.py --dry-run`.

2. **Run the dashboard** (from repo root):
   ```bash
   cd dashboard && npm install && npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173). Click **Load from server** to show results from `collector/scan-results.ndjson`.

## Loading data

- **Load from server** — Fetches NDJSON from the local API (default file: `../collector/scan-results.ndjson`). Requires the dashboard dev server to be running (it starts automatically with `npm run dev`).
- **Load file…** — Pick an NDJSON file from your machine. Works without the API server.

To point the server at a different file:
```bash
NDJSON_PATH=/path/to/events.ndjson node server.js
```
Then run Vite in another terminal: `npm run dev:vite`, and use **Load from server**.

## Scripts

| Command | Description |
|--------|-------------|
| `npm run dev` | Start Vite + API server (recommended for demo) |
| `npm run dev:vite` | Vite only; use **Load file…** to open NDJSON |
| `npm run build` | Build static assets to `dist/` |
| `npm run server` | Run only the API server (port 3001) |
| `npm start` | Build and serve app + API (port 3001) |

## What it shows

- **Endpoint**: ID, OS, posture, last scan time (from events).
- **Detected tools**: Tool name, class (A/B/C), confidence band (Low/Medium/High), policy decision (Detect / Warn / Approval Required / Block), and reason/summary from the canonical event schema.

No auth; for local/demo use only.
