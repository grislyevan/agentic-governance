# Detec LinkedIn Content Bank

Reusable copy and calendar for the Detec company page. Voice and proof points align with [brand-voice-guide.md](../brand-voice-guide.md), [about-detec.md](../about-detec.md), and [capability-brief.md](../capability-brief.md). No links in post body; put link in first comment if needed. 3–5 hashtags per post. Respond to every comment in the first 60 minutes.

---

## 1. Company page profile copy

### Headline (paste into LinkedIn company page)

See what AI agents do. Govern what they're allowed to. Endpoint governance for agentic AI tools.

### About section (pick one hook for line 1)

**Hook option A (line 1):**  
Your developers are already using agentic AI tools. Security teams weren't built to see what they're doing.

**Hook option B (line 1):**  
Application blocklists break when tools rename, wrap, or run locally. We detect by what they do, not what they're called.

**Paragraph 1:**  
Detec discovers and controls autonomous AI tools on developer endpoints. Every detection is confidence-scored and policy-driven: visibility, warning, approval required, or block. We give security teams honest, evidence-based visibility so they can govern proportionally instead of guessing or blocking blindly.

**Paragraph 2:**  
We build for SOC, Security Ops, and IT. You get visibility into what's running, an audit trail for every decision, and an enforcement ladder you control. Low-risk tools get visibility. High-risk tools get gates. Your policy defines the thresholds.

**Paragraph 3:**  
12 tools across 4 capability classes. Five signal layers. Lab-validated detection. We publish our known limits and test for evasion, because transparency about what we can't do builds more trust than perfection claims.

**Last line (CTA):**  
Follow for visibility into agentic AI on endpoints.

**Alternative CTA:**  
Follow for evidence-based endpoint governance.

### Banner

Use Detec visual identity (logo + tagline or "Endpoint governance for agentic AI"). See [logo-usage-guidelines.md](../logo-usage-guidelines.md) and [color-palette-reference.md](../color-palette-reference.md).

### Featured

When available: link to detecadg.com; one-sheet or capability brief if hosted; one top-performing post.

---

## 2. Hook variants (first line only; pick one per post)

- **Curiosity / gap:** Your developers are already using agentic AI tools. Can your security team see what they're doing?
- **Bold claim:** Blocklists fail the moment a tool renames itself. Here's what actually works.
- **Specific:** Five signal layers. No single one drives enforcement. Here's how we score every detection.
- **Question:** How do you govern Claude Code and Cursor when they're not in your asset inventory?
- **Problem frame:** Application blocklists don't work when the tool renames, wraps, or runs locally. The risk isn't the product name. It's autonomous code execution on the endpoint.

---

## 3. Full post drafts

### Draft 1: Problem frame (blocklists fail)

**Hook (use as first line):**  
Application blocklists don't work when the tool renames, wraps, or runs locally. The risk isn't the product name. It's autonomous code execution on the endpoint.

**Body:**  
Claude Code can execute shell commands on developer machines. Cursor spawns agent processes that write to the filesystem. Ollama runs locally with no cloud visibility. These tools are already on your endpoints. Blocking by product name works until someone renames the binary, wraps it in a script, or runs it in a container. Then you're playing whack-a-mole while the real risk, autonomous code execution, goes ungoverned. We detect by capability class, not by name. When a new tool appears, it maps into an existing class and inherits your policy. No signature update. No waiting for vendor coverage. What's your team using to get visibility?

**Hashtags:** #SecOps #endpointsecurity #AIgovernance #devsecops #infosec

---

### Draft 2: Data / proof post (12 tools, 5 layers)

**Hook (use as first line):**  
12 tools. 5 signal layers. One confidence score. Here's how we decide what gets detected, warned, or blocked.

**Body:**  
We classify agentic AI tools by what they do: SaaS copilots (Cursor, Copilot, Continue), local runtimes (Ollama, LM Studio), autonomous executors (Claude Code, Aider, Open Interpreter, GPT-Pilot, Cline), and persistent agents (OpenClaw). Every detection is built from five layers: process, file, network, identity, and behavior. No single signal drives enforcement. The result is a confidence score from 0.00 to 1.00, explainable and auditable. Your policy then maps that score and the tool class to four states: Detect, Warn, Approval required, or Block. Low risk gets visibility. High risk gets gates. Save this for the next time someone asks how you govern agentic AI on endpoints.

**Hashtags:** #SecOps #endpointsecurity #AIgovernance #devsecops #infosec

---

### Draft 3: Known limits / trust post

**Hook (use as first line):**  
We publish what we can't do. Containerized dev reduces host telemetry. Short-lived HTTPS needs EDR for process attribution. Evasion is possible. We test for it and document it.

**Body:**  
Trust is earned, not assumed. So we document known limits: where detection confidence varies, where visibility is partial, and which evasion vectors we've tested. Containerized or remote dev can reduce process and file signals. Polling alone can't reliably attribute short-lived HTTPS bursts to a specific process; EDR or kernel telemetry improves that. Renamed binaries and wrapper scripts require behavior-layer correlation. We run lab validation and evasion tests, and we publish the results. Transparency about what we can't do builds more trust than perfection claims. What would you add to the list?

**Hashtags:** #SecOps #endpointsecurity #AIgovernance #infosec #trust

---

### Draft 4: Enforcement ladder (explain one thing)

**Hook (use as first line):**  
The enforcement ladder has four states. Detect. Warn. Approval required. Block. Your policy decides where each tool lands.

**Body:**  
Detect means visibility only. No user disruption; you see what's running and you have the audit trail. Warn means the operator is notified and policy awareness is created. Approval required means someone has to sign off before the action proceeds. Block is a hard stop. We don't choose the state for you. Your policy maps confidence score, tool class, asset sensitivity, and action risk to one of these four. Low-risk tools on non-sensitive assets typically land at Detect or Warn. High-risk actions on sensitive assets land at Approval required or Block. Governance is a spectrum, not a switch. What would you add?

**Hashtags:** #SecOps #endpointsecurity #AIgovernance #devsecops #infosec

---

### Draft 5: Lab / evidence post (16 runs)

**Hook (use as first line):**  
We run lab validation on every tool we detect. 16 runs. Confidence scores, signal breakdowns, evasion tests. Here's one thing we learned.

**Body:**  
Class C tools don't all look the same. Claude Code is file-anchored: strong artifact footprint, process clarity. Open Interpreter is behavior-anchored: generic process name, almost no persistent state. Same class, different detection profile. So we calibrate weights per tool and we validate with real installs and agentic sessions. We've completed 16 lab runs across multiple tools and platforms. The takeaway: policy can be class-based, but detection quality depends on tool-specific calibration and honest limits. We publish both. What's the one thing you'd want to see in a lab report before you trust a detection?

**Hashtags:** #SecOps #endpointsecurity #AIgovernance #devsecops #infosec

---

## 4. 30-day content calendar (2–3 posts per week)

| Week | Mon | Wed | Fri |
|------|-----|-----|-----|
| 1 | Pillar 1: "Five signal layers" explainer (detection that shows its work) | Pillar 2: "Four states: Detect, Warn, Approve, Block" (use Draft 4) | Pillar 3: "We publish our known limits" (use Draft 3) |
| 2 | Data post: "12 tools, 4 classes" (use Draft 2) | Problem frame: "Blocklists break when tools rename or run locally" (use Draft 1) | Operator: "Every detection is an auditable record. Here's what's in it." |
| 3 | Pillar 1: "Why we score confidence, not yes/no" | Pillar 2: "Low risk gets visibility. High risk gets gates." | Lab/evidence: "What we learned from 16 lab runs" (use Draft 5) |
| 4 | Problem frame: "Repo-destructive coding agents run shell and write files. Visibility first." | Data post: Different angle (e.g. SIEM, events, audit trail) | Pillar 3: "Evasion is possible. We test for it and document it." (variant of Draft 3) |

After 30 days: repurpose the top-performing post into a carousel (Slide 1 = hook, one insight per slide, last = CTA + follow).

---

## 5. Hashtag set

**Default set (3–5 per post):**  
#SecOps #endpointsecurity #AIgovernance #devsecops #infosec

**Optional swap-ins when topic fits:**  
#CISO #SOC #shadowIT #compliance #detection

Use no more than 5 hashtags per post. Prefer the default set for consistency.

---

## 6. Carousel structure (native document)

- **Slide 1:** Same hook rules (curiosity / bold claim / specific). One idea only.
- **Slides 2–5:** One insight per slide. Examples: "Class A: SaaS copilots"; "Class C: Autonomous executors"; "Confidence 0.00–1.00"; "Your policy, your thresholds."
- **Final slide:** "Follow Detec for endpoint governance for agentic AI" + "Save this for [specific moment]."

---

## 7. Getting the first followers (reminder)

- Add "Follow us on LinkedIn" and company page link on detecadg.com (footer or pilot/contact page).
- Team: follow the company page, list as employer if appropriate, share 1–2 key posts with a genuine one-line comment.
- Comment strategy: leave substantive comments (2–3 sentences) on posts about agentic AI, endpoint visibility, or SOC workflow. Don't pitch; some will click through to the company page.
- Consistency: 8–12 posts in 30 days with profile optimized so the page is credible when evaluators or future traffic arrives.
