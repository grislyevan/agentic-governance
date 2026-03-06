# Detec: Sales Pitch

**See what AI agents do. Govern what they're allowed to.**

---

## The Problem No One's Tracking

Your developers are already using agentic AI tools. Claude Code can execute shell commands on laptops. Cursor can spawn agent processes that write directly to the filesystem. Someone is running Ollama locally with no cloud visibility and no audit trail. These are not autocomplete suggestions. They are autonomous tools that can run code, access networks, and modify files, and they are being adopted faster than security can inventory them.

Most teams try to manage this with application blocklists. That works until a tool renames itself, wraps inside another process, or runs entirely locally. You end up playing whack-a-mole with product names while the real risk, autonomous code execution on endpoints, goes ungoverned.

The question is not whether your developers are using these tools. They are. The question is whether you can see what they are doing and govern it proportionally.

---

## What Detec Does

Detec is a lightweight endpoint agent that detects agentic AI tools by what they do, not what they are called. It runs as a persistent service on the endpoint and reports events to a central API.

Instead of maintaining a list of product names, Detec classifies tools by capability:

- SaaS copilots and IDE agents such as Cursor and GitHub Copilot
- Local model runtimes such as Ollama and LM Studio
- Autonomous executors such as Claude Code and Open Interpreter
- Persistent agents that operate continuously

The key insight is that policy targets the capability class, not the product name. When a new tool appears, and it will, it maps into an existing class and inherits existing policy automatically. No signature update. No waiting for vendor coverage.

Today, Detec covers eleven tools across four capability classes, with more in development.

---

## How It Decides

Detec builds detections from five signal layers:

- Process lineage
- File artifacts
- Network connections
- Identity context
- Behavioral patterns

No single signal drives enforcement. Each layer contributes evidence with a strength value.

The confidence engine applies per-tool calibrated weights. Process evidence may matter more for one tool. File artifacts may matter more for another. The engine also applies explicit penalties when evidence is weak or ambiguous. The output is a confidence score from zero to one, and it is explainable. You can trace the score back to the exact processes, files, connections, and behaviors that contributed.

### Enforcement: proportional by design

The policy engine evaluates:

- Confidence score
- Capability class
- Asset sensitivity tier
- Action risk level

Rules are deterministic, versioned, and auditable with a stable rule ID and explainability payload. The output is one of four states:

- **Detect.** Visibility only.
- **Warn.** Notify IT or SecOps while the developer keeps working.
- **Approval required.** Explicit sign-off to continue.
- **Block.** Hard stop.

You set the thresholds. Low risk gets visibility. Medium risk triggers warnings. High risk requires approval. Policy violations get blocked. Friction remains proportional to risk.

---

## Why This Is Different

**Governance by capability, not product names.** Blocklists break when a tool renames, forks, or wraps. Detec's class-based model makes policy durable. A new autonomous executor receives the same controls as every other autonomous executor automatically.

**Every decision is scored, not binary.** Most tools give you yes or no. Detec gives you a confidence score with a full evidence chain. You can see which layers matched, how much each contributed, and what penalties applied when evidence was incomplete. This matters when a SOC analyst must explain a decision to an engineering lead, or when compliance needs an audit trail that holds up.

**Honest limits.** Some environments reduce visibility, including containerized development flows and short-lived network connections without EDR integration. Evasion is possible. We test for it, document known vectors, and use multi-signal correlation to raise the cost. Trust is earned, not claimed.

---

## How It Fits

Detec runs on endpoints as a background service, scanning at a configurable interval. In steady state it reports only material changes:

- A new tool appears
- A tool's class escalates
- Confidence crosses a threshold band
- Enforcement state changes

If connectivity drops, events queue locally and flush on reconnect.

The central API ingests events per tenant and feeds the dashboard. Operators can see what is running, where, with what confidence, which signals contributed, which rule fired, and what enforcement applied.

---

## See It Work

Deploy the agent to a small set of endpoints. Within one scan cycle you will see:

- Which agentic AI tools are active
- Which capability class each maps to
- The confidence score and evidence chain
- The policy outcome

Compare it to your current inventory. Sanity-check the scores. Review the evidence and penalties. Then decide whether the governance model fits your organization.
