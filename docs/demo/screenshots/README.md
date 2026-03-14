# Demo screenshots

This folder holds screenshots that show the product proving the value in about five minutes. Capture them by running the [five-minute demo](../demo.md) (or `scripts/demo-five-min.sh`), logging in, and saving the views below.

## Required shots (3–5)

1. **Dashboard (summary)**  
   File: `01-dashboard-summary.png`  
   View: Main dashboard with summary cards (Endpoints, Detect, Warn, Approval required, Blocked). At least one "Blocked" count and the endpoints list visible.  
   Story: "Here is the operator view: endpoints and decision counts at a glance."

2. **Events (one block)**  
   File: `02-events-block.png`  
   View: Events page with one event selected. The event should show decision "Block," rule ID (e.g. ENFORCE-005), tool name (e.g. Claude Code), and summary.  
   Story: "Here is a concrete block event with rule and evidence."

3. **Policies**  
   File: `03-policies.png`  
   View: Policies page with at least one block rule visible (e.g. ENFORCE-005 or ENFORCE-D01) and its description readable.  
   Story: "Here is the policy that produced the block; rules are auditable and versioned."

4. **Login (optional)**  
   File: `04-login.png`  
   View: Login screen.  
   Story: "Entry point for the demo."

5. **Audit log (optional)**  
   File: `05-audit-log.png`  
   View: Audit log with at least one enforcement or policy event.  
   Story: "Every decision is logged for compliance and review."

## How to capture

1. Run `./scripts/demo-five-min.sh` from repo root (or follow [docs/demo.md](../demo.md)).
2. Open http://localhost:8000 and log in (e.g. admin@example.com / change-me).
3. If no demo data appears, log in as owner and call `POST /api/demo/reset` (or use the demo reset in Settings if available).
4. Navigate to each view and take a screenshot. Name files as above and place them in this directory.

## Five-minute story

The screenshots, in order, tell the story: login, see the dashboard with blocked count, open one blocked event to see tool/rule/summary, open policies to see the rule that fired, and optionally show the audit trail. Together with [sample-events.json](../sample-events.json) and [block-decision-example.md](../block-decision-example.md), they prove the product in about five minutes.
