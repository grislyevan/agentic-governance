# Detec — Brand Voice Guide

**Product:** Detec — endpoint governance for agentic AI tools
**Tagline:** See what AI agents do. Govern what they're allowed to.
**Personality:** Modern & Approachable — security that feels like a well-built developer tool
**Primary buyer:** SOC Manager / Security Ops / IT
**Name origin:** Truncated from "detect." The missing letter is the brand — intentional, modern, clear. Detection is where governance starts.

---

## Voice Principles

### 1. Show the score, not the scare

Lead with confidence scores and evidence, not fear. Detec is a tool for informed decisions, not a panic button.

- **Do:** "Claude Code found on 3 endpoints with 0.87 confidence"
- **Don't:** "CRITICAL: Unauthorized AI detected across your infrastructure"

### 2. Operator-first language

Write for the person using this every day. Respect their time. Skip the jargon ladder.

- **Do:** "This endpoint has 3 agentic tools detected"
- **Don't:** "Our advanced multi-signal attribution engine has correlated telemetry across five detection layers to identify anomalous agentic tool presence"

### 3. Earned trust

When we don't know, we say so. Known limits are a feature, not a bug. This aligns with the product's Honest Gaps philosophy — transparency builds more trust than perfection claims.

- **Do:** "Network attribution for short-lived connections requires EDR integration — polling alone can't reliably link these to a specific process"
- **Don't:** "Complete network visibility across all connection types"

### 4. Progressive, not punitive

The enforcement ladder is a conversation, not a hammer. The product helps teams govern proportionally.

- **Do:** "Your policy defines the friction level. Low-risk tools get visibility. High-risk tools get gates."
- **Don't:** "Block all unauthorized AI tools instantly"

### 5. Precise but human

Use measured language. Every claim should be defensible. But don't sound like a legal filing.

- **Do:** "Governance controls for 11 agentic AI tools, with more in development"
- **Don't:** "Complete AI governance solution" (overpromise)
- **Don't:** "Subject to the tool detection profiles enumerated in Section 4 of the operational playbook" (legalese)

---

## Tone Spectrum

| Context | Tone | Example |
|---|---|---|
| Dashboard UI | Calm, factual, scannable | "3 tools detected · 1 warning · 0 blocks" |
| Alert/notification | Clear, direct, actionable | "Claude Code on dev-mac-04 exceeded policy threshold. Review required." |
| Marketing site | Confident, accessible, honest | "Multi-signal detection with confidence scoring. No single signal drives enforcement alone." |
| One-sheet / sales | Evidence-backed, concise, trustworthy | "11 tools across 4 risk classes. Every decision scored and auditable." |
| Error / failure state | Helpful, non-blaming | "Couldn't reach the API. Events are queued locally and will sync when connection resumes." |
| Documentation | Clear, structured, example-driven | "The collector scans five signal layers. Here's what each one captures." |

---

## Language Choices

### Preferred Terms

| Use | Instead of |
|---|---|
| detected | discovered, found, caught |
| governance | control, restriction, policing |
| confidence score | risk score, threat score |
| enforcement state | block status, restriction level |
| progressive controls | escalation, sanctions |
| signal layers | detection dimensions, telemetry sources |
| agentic AI tools | AI threats, shadow AI, rogue AI |
| policy decision | enforcement action, security response |
| known limits | caveats, disclaimers |
| evidence | proof, artifacts |

### Words to Avoid

| Word | Why |
|---|---|
| threat | Positions AI tools as adversarial; they're tools being governed |
| shadow IT | Loaded term; we prefer "ungoverned" or "unmanaged" |
| eliminate / eradicate | We don't claim to eliminate anything |
| comprehensive / complete | Overpromise; use "covers X tools" with specifics |
| cutting-edge / best-in-class | Empty superlatives |
| revolutionary / game-changing | Hype language that erodes trust |
| seamless / frictionless | Governance inherently introduces proportional friction — that's the point |
| AI-powered (about Detec itself) | We govern AI tools; describing ourselves as "AI-powered" creates confusion |

---

## Naming Conventions

### Product Name
- Full: **Detec**
- Never: "The Detec," "Detec Platform," "Detec AI"
- In a sentence: "Detec finds agentic AI tools on your endpoints"
- With descriptor (when needed): "Detec — endpoint governance for agentic AI"

### Component Names
- **Detec Collector** — the endpoint agent
- **Detec Dashboard** — the web UI
- **Detec API** — the backend service
- Follow the pattern: "Detec [Component]"

### Feature Language
- Detection profiles, not "signatures" or "rules"
- Tool classes (A/B/C/D), not "risk levels" or "tiers"
- Enforcement ladder, not "response chain" or "escalation path"
- Confidence bands, not "risk ratings"

---

## Buyer Objection Voice Patterns

When handling common buyer objections, maintain the voice principles:

| Objection | Voice-Consistent Response |
|---|---|
| "Everyone claims multi-signal" | "Our confidence scores are traceable — each detection links to the specific signals that contributed. You can see the process, file, network, identity, and behavior evidence behind every score." |
| "Won't this block developers?" | "The enforcement ladder has four levels. Most tools land at Detect or Warn — visibility without friction. Your policy decides where the gates go." |
| "What about tools you don't cover?" | "We cover 11 tools across 4 risk classes today. The class-based model means new tools map to existing policy — a new autonomous executor gets Class C controls automatically." |
| "How do I trust your detection?" | "We publish lab run results, evasion test findings, and an honest gaps brief. If a signal has a known blind spot, we document it." |

---

## Tagline and Supporting Copy

**Primary tagline:**
See what AI agents do. Govern what they're allowed to.

**Supporting one-liners** (for different contexts):
- "Endpoint governance for agentic AI tools" — descriptor line
- "Confidence-scored decisions for every AI action" — technical differentiator
- "Detection is just the start. Governance is the point." — brand story
- "11 tools. 5 signal layers. Every decision auditable." — proof-point
