# Detec — Social Content Drafts

Created: 2026-03-25
Context: Initial awareness push. Goal is category definition + credibility, not lead gen yet.
Rule: Share the what and why. Keep the how much.

---

## Reddit

### Post 1: r/cybersecurity — "I built a thing"

**Title:** I built an endpoint agent that detects agentic AI tools by what they do, not what they're called

**Body:**

Hey everyone. I've been building something for the last few months and wanted to share it with this community since you're the people I'd want feedback from.

**The problem I kept running into:**

Developers on my team were using Claude Code, Cursor, Ollama, and a bunch of other AI tools. Some of these tools can execute shell commands autonomously, write to the filesystem, open network connections — they're not autocomplete anymore. They're agents.

I tried to get visibility using standard controls. Here's what I found:

- EDR sees processes but can't reliably attribute activity to a specific agentic tool
- CASB sees cloud traffic but misses anything running on localhost
- App inventory shows what's installed but not what's executing autonomously at runtime
- Firewalls see outbound connections but not local model inference

So I started building a detection agent specifically for this category.

**What it does:**

Instead of maintaining a blocklist of product names (which breaks the moment something renames or wraps), it classifies tools by capability:

- Class A: SaaS copilots (Cursor assistive, Copilot, Continue)
- Class B: Local runtimes (Ollama, LM Studio)
- Class C: Autonomous executors (Claude Code, Open Interpreter, Aider)
- Class D: Persistent agents

It scans five signal layers — process, file, network, identity, behavior — and produces a confidence score from 0 to 1. No single signal drives enforcement. The score is explainable: you can trace it back to exactly which signals contributed and how much.

Then a policy engine maps the score + tool class + asset sensitivity to one of four states: detect (visibility only), warn, approval required, or block. Your policy decides where tools land. It enforces the decision.

**What I'm NOT claiming:**

- This doesn't eliminate evasion. Someone determined enough can evade. We test for evasion, document the vectors, and use multi-signal correlation to make it more expensive. But claiming "impossible to evade" would be dishonest.
- Containerized and remote dev environments reduce visibility. Host-level telemetry has limits when the tool runs inside a container.
- Some detections land at medium confidence today, not high. Short-lived network connections without EDR integration are hard to attribute reliably.

I'm publishing these limits because I think security tooling that hides its blind spots is worse than no tooling at all. You should know where the edges are.

**Current state:** 11 tools across 4 classes, 5 signal layers, confidence-scored enforcement with full audit trail. Every detection event is a canonical JSON designed for SIEM ingestion.

Interested in feedback from anyone dealing with this problem. Happy to answer technical questions about the detection model or the policy engine.

---

### Post 2: r/blueteam — Discussion starter

**Title:** How is your team handling agentic AI tool governance on endpoints?

**Body:**

Genuine question. Not selling anything, just trying to understand where everyone's at.

We've been dealing with a growing number of AI tools on developer endpoints that go beyond autocomplete — Claude Code can run shell commands, Cursor has an agent mode, Ollama runs full models locally. These tools can write files, open connections, and execute code autonomously.

The challenge I keep hitting:

1. App-name blocklists are brittle. Tool renames, forks, or wraps inside another process and the blocklist is useless.
2. EDR captures processes but doesn't know it's looking at an "agentic AI tool" — it just sees node or python.
3. Most of this runs locally so CASB never sees it.
4. Telling developers "don't use AI tools" is not realistic.

I ended up building a detection layer specifically for this — classifies by capability (copilot vs local runtime vs autonomous executor), scores confidence across multiple signals, and applies proportional policy (not just block everything).

But I'm curious: is anyone else actively governing this category? Or is it still in the "we'll deal with it later" bucket for most teams?

---

## LinkedIn

### Post 1: Category Definition — The Problem

Your developers are already using agentic AI tools.

Not autocomplete. Not suggestions. Tools that execute shell commands autonomously. Tools that write to the filesystem. Tools that open network connections, run local model inference, and spawn agent processes — all on your endpoints.

Claude Code runs shell commands. Cursor has an agent mode that writes directly to disk. Ollama runs language models locally with zero cloud visibility.

Here's what your current security stack sees:

EDR: a process called "node" is running.
CASB: nothing (it's localhost).
App inventory: "Cursor is installed."
Firewall: outbound HTTPS to api.anthropic.com.

Here's what none of them tell you: which tool is operating autonomously, what capability class it falls into, how confident you should be in that detection, and what your policy says to do about it.

This is a governance gap. Not because your tools are broken — they were built for a different category. Agentic AI tools behave like legitimate developer activity, run locally, and shift between assistive and autonomous modes at runtime.

The question isn't whether to allow them. It's whether you can see what they're doing and govern it proportionally.

We built Detec to answer that question.

#agenticAI #endpointsecurity #AIgovernance #cybersecurity #infosec

---

### Post 2: The Honest Limits Post — Differentiator

Every security vendor says "comprehensive coverage."

Here's what we say instead:

Detec covers 11 agentic AI tools across 4 capability classes today. Not "all AI tools." Eleven. We'll tell you which ones.

Our detection confidence varies by tool and environment. High-risk autonomous executors like Claude Code typically report at Medium confidence on standard endpoints — process and file evidence anchor the score, but network and behavioral layers improve significantly with EDR integration. We'll tell you the confidence band and exactly which signals contributed.

Containerized development environments reduce host-level visibility. We document this as a known limit, not something we quietly hope you don't notice.

Evasion is possible. We test evasion vectors, publish the results, and use multi-signal correlation to raise the cost. But we don't claim it's impossible.

Why publish our own limits?

Because security teams making governance decisions need to know where the edges are. A confidence score is only useful if you trust the system producing it. And trust is earned by being transparent about what works and what doesn't — not by claiming capabilities you can't consistently deliver.

We think the industry has it backwards. Hiding blind spots doesn't make your product look stronger. It makes every customer who discovers them feel misled.

Detec: endpoint governance for agentic AI tools.

#cybersecurity #AIgovernance #infosec #transparency #endpointsecurity

---

### Post 3: The Technical Insight — How Detection Should Work

Most security tools detect software by name. That works until it doesn't.

An AI coding tool renames its binary. A fork ships under a different brand. A tool wraps itself inside an IDE extension. An open-source project has twelve forks with twelve names.

Now your blocklist is a maintenance treadmill.

We took a different approach with Detec. Instead of asking "what is this called?" we ask "what can this do?"

The answer maps to a capability class:

Class A: SaaS copilots — assistive, cloud-connected
Class B: Local runtimes — inference on the endpoint, no cloud required
Class C: Autonomous executors — can run code, write files, open connections independently
Class D: Persistent agents — continuous autonomous operation

Policy targets the class, not the name. When a new tool appears — and it will — it maps to an existing class and inherits existing policy. No signature update. No waiting for a vendor to add coverage.

A new autonomous executor gets Class C controls automatically. Because what makes it risky isn't what it's called. It's what it can do.

#cybersecurity #detectionengineering #AIgovernance #endpointsecurity

---

### Post 4: The Outcome Post — Short and punchy

Deployed to 20 developer endpoints for a pilot.

Within one scan cycle:
- 6 agentic AI tools detected across 3 capability classes
- 2 tools the security team didn't know were running
- 1 autonomous executor on a Tier 2 asset — flagged for approval

Every detection scored, every signal traceable, every policy decision auditable.

Before: "We think developers use Copilot."
After: "6 tools, 3 classes, 2 unknown, 1 policy escalation — all with evidence chains."

That's the difference between guessing and governing.

#AIgovernance #endpointsecurity #cybersecurity #detec

---

### Post 5: The "Why Now" Post

The window for agentic AI governance is open right now. It won't stay open.

Here's the timeline:

2024: AI coding assistants became mainstream. Mostly autocomplete. Low risk.
2025: Agentic mode arrived. Claude Code, Cursor agent mode, Open Interpreter. Tools that execute, not just suggest.
2026: Autonomous tool adoption is accelerating faster than security teams can inventory.

Right now, no Gartner category exists for this. No standard RFP template. Most CISOs don't have a budget line item for "agentic AI governance."

That means whoever defines the category shapes the conversation.

Within 18-24 months, major EDR and endpoint vendors will bolt on basic AI tool detection. It'll be binary (detected/not detected), product-name-based (brittle), and lack confidence scoring (trust us, it's bad).

The opportunity right now is to build something better before "good enough" arrives. Capability-class detection. Confidence-scored decisions. Proportional enforcement. Auditable evidence chains.

That's what we're building at Detec. And we're publishing our known limits along the way — because the category deserves to start with honesty, not hype.

#AIgovernance #cybersecurity #startups #infosec

---

## Reddit: r/ClaudeAI

### Post 3: "Built with Claude Code" angle

**Title:** I used Claude Code to build an endpoint agent that detects (and governs) agentic AI tools like Claude Code itself

**Body:**

Bit of an ouroboros situation here — I used Claude Code extensively to build a security tool that, among other things, detects Claude Code running on developer endpoints.

**What I built:**

Detec is a lightweight endpoint agent that finds agentic AI tools by what they can do, not what they're called. Instead of a blocklist of product names (which breaks the moment something renames or forks), it classifies tools into capability classes:

- Class A: SaaS copilots (Cursor, Copilot)
- Class B: Local runtimes (Ollama, LM Studio)
- Class C: Autonomous executors (Claude Code, Open Interpreter, Aider)
- Class D: Persistent agents

It scans five signal layers (process, file, network, identity, behavior), produces a confidence score from 0 to 1, and feeds that into a policy engine with four enforcement states: detect, warn, approval required, or block.

Covers 11 tools today. Every detection is scored, explainable, and auditable. Free to try.

**How Claude helped:**

Claude Code was involved in most of the development across the collector (Python), the API (FastAPI), and the React dashboard. Specifically:

- The detection profiles for each tool — Claude helped research the process signatures, file artifacts, and network patterns for each of the 11 tools
- The confidence scoring engine — iterating on the weighting and penalty model across dozens of test scenarios
- The policy engine rules — working through the combinatorics of class + confidence + sensitivity + risk
- Sprint planning and code review — I ran three remediation sprints largely through Claude Code sessions
- The branding and sales materials — voice guide, whitepaper, one-sheet, all developed in conversation

Honestly, this project would have taken 3-4x longer without Claude Code. The ability to work through complex detection logic interactively, have it write tests, and iterate on scoring models in real-time was a massive accelerator.

**The ironic part:**

Claude Code is classified as Class C (Autonomous Executor) in Detec's taxonomy. It can run shell commands, write files, and operate with significant autonomy. So the tool that helped me build the governance system is itself one of the highest-risk tools the system governs.

I think that's actually the point. These tools are incredibly powerful and productive. The answer isn't to block them — it's to have visibility into what's running, score the confidence, and apply proportional governance. Developers keep their tools. Security gets an audit trail.

Happy to answer questions about the detection model, the build process with Claude Code, or anything else.

---

## Twitter / X

### Thread 1: The Problem (5 tweets)

**1/**
Your developers are running AI tools that execute shell commands autonomously on their laptops.

Your EDR sees "node is running."
Your CASB sees nothing.

That's the governance gap for agentic AI. A thread on why existing controls miss it:

**2/**
The problem isn't your security stack. It's the category.

Agentic AI tools look like normal dev activity. They run as child processes of IDEs. They use localhost. They spawn and die in seconds.

EDR, CASB, DLP, app inventory — none were designed for tools that blur the line between developer and autonomous agent.

**3/**
App-name blocklists are the common response. Here's why they fail:

Tool renames → blocklist miss
Tool forks → new name, same risk
Tool wraps inside IDE → invisible to blocklist
Tool runs locally → no cloud signal to block

You're playing whack-a-mole with product names while the real risk — autonomous code execution — goes ungoverned.

**4/**
The fix isn't better blocklists. It's detection by capability.

What CAN this tool do?
- Just suggest code? → Low friction
- Execute commands? → Needs governance
- Run continuously and autonomously? → Needs approval

Policy should target capability class, not product name. New tool appears → maps to existing class → inherits policy automatically.

**5/**
This is what we built Detec to do.

5 signal layers. Confidence-scored. Proportional enforcement. Auditable.

And we publish our known limits — because security tools that hide blind spots are worse than no tools at all.

More soon.

---

### Thread 2: Honest Limits (3 tweets)

**1/**
Hot take: security vendors should publish their blind spots.

At Detec, we do. Here are ours:

- Containerized dev environments reduce host-level visibility
- Short-lived network bursts are hard to attribute without EDR integration
- Evasion is possible. We test for it. We don't claim it's impossible.

**2/**
Why would we publish this?

Because a SOC analyst making a governance decision based on our confidence score needs to know where the edges are.

"0.72 confidence" means nothing if you don't trust the system producing it. Trust comes from transparency, not from hiding caveats in footnotes.

**3/**
Every security vendor says "comprehensive."

We say: 11 tools, 4 classes, 5 signal layers, and a list of known limits we update regularly.

That's harder to market. But it's easier to trust.

---

### Single Posts (standalone)

**A.**
"How many agentic AI tools are running on your developer endpoints right now?"

If the answer is "I don't know" — that's the problem we built Detec to solve.

**B.**
Blocklists detect product names.
Detec detects capabilities.

One breaks when tools rename.
The other doesn't.

**C.**
Detection isn't governance.

Knowing a tool exists isn't the same as knowing what it can do, how confident you are, and what your policy says about it.

Governance = detection + classification + confidence + proportional enforcement + audit trail.

**D.**
Security tools that claim zero blind spots have infinite blind spots they're not telling you about.

---

## Posting Notes

**LinkedIn timing:** Tue-Thu, 8-10am local time for target audience (US East/West). Avoid Monday and Friday.

**Reddit rules:**
- r/cybersecurity allows self-promotion if you're contributing genuinely. Engage in comments. Answer questions. Don't just post and disappear.
- r/blueteam is more discussion-oriented. Post 2 is designed for this.
- Never link to your product in the first post. Let people ask.

**Twitter/X:**
- Threads perform best when tweet 1 is a standalone hook. Someone should want to RT tweet 1 even without reading the rest.
- Space threads across 2-3 minutes, not all at once.
- Single posts (A-D) are evergreen — schedule across weeks, not days.

**Cross-posting order:** Reddit first (build credibility, get feedback), then LinkedIn (thought leadership), then Twitter/X (amplify what resonated).

**What never to reveal in comments/replies:**
- Per-tool weight values or calibration specifics
- That evasion attempts boost the confidence score
- Infrastructure floor logic
- Specific detection indicators (file paths, process signatures, network patterns)
- Named scanner details

If someone asks about scoring internals, safe answer: "The confidence engine uses per-tool calibrated weights across five signal layers, with penalties for missing evidence. The specifics are proprietary, but the output is fully explainable — you can see which layers contributed and how much."
