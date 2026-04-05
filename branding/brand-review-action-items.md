# Detec — Brand Review Action Items

Reviewed: 2026-03-25

---

## Visual Identity

### 1. Logo metaphor — pressure-test with buyers
**Issue:** The aperture/pinwheel mark reads as camera/media, not detection or governance. SOC operators may not connect the visual to the product domain.
**Action:** Test the current mark and at least one alternative concept with 3-5 target buyers. Ask unprompted: "What does this logo suggest to you?" If "camera" or "media" comes up more than "security" or "detection," revisit the mark.

### 2. Logo colors diverge from brand palette
**Issue:** The mark introduces sky blue and orange gradients not present in the documented color system (indigo/teal/amber). The logo and the design system tell different color stories.
**Action:** Either update the color palette to include the logo's blues and oranges as official brand colors, or adjust the mark to use only documented palette colors. One system, one source of truth.

### 3. Wordmark typeface undocumented
**Issue:** The "Detec" wordmark in the lockup doesn't appear to be IBM Plex Sans. The typography guide doesn't mention what font the wordmark uses.
**Action:** Document the wordmark typeface, weight, and any modifications (tracking, optical adjustments) in the typography guide. Add a rule: "Do not recreate the wordmark in IBM Plex Sans — use the provided asset."

---

## Brand System Completeness

### 4. Brand foundation document missing from canon
**Issue:** Purpose, vision, mission, and values are never explicitly stated. The typography doc references `brand-foundation.md` but it only exists in worktree copies, not the main `branding/` directory.
**Action:** Consolidate and move `brand-foundation.md` into the main branding directory. This is the strategic layer everything else hangs from.

### 5. Logo usage guidelines missing from canon
**Issue:** `logo-usage-guidelines.md` exists only in worktrees. Clear space, minimum sizes, background rules, and "don't" examples are not in the primary directory.
**Action:** Consolidate and move logo usage guidelines into the main branding directory.

### 6. Consolidate worktree-only documents
**Issue:** Several documents exist only in worktree copies: `brand-foundation.md`, `logo-usage-guidelines.md`, `one-sheet.md`, `whitepaper.md`, `capability-brief.md`. The main `branding/` directory is missing canonical versions.
**Action:** Audit worktree branding files against the main directory. Promote the most current versions to the main `branding/` directory.

---

## Dashboard vs. Brand Aspiration

### 7. Resolve the "Linear or CrowdStrike" question
**Issue:** The voice guide aspires to "Tailscale / Linear territory" — light, modern, approachable. The dashboard screenshot is dark navy with dense information, closer to CrowdStrike territory. Both are valid, but they're different brands.
**Action:** Decide which direction the product UI actually takes. If dark mode is the primary experience (common for SOC tools), update the brand personality description to reflect that honestly. If the aspiration is truly Linear-like, the dashboard needs a design pass.

---

## Brand Protection

### 8. Create an honest-limits publishing gate
**Issue:** The "honest limits" philosophy is the brand's single most differentiating asset. It only works if every piece of content follows through. One "comprehensive coverage" claim in a slide deck undermines the whole position. There's no process to catch this.
**Action:** Create a short pre-publish checklist (5-10 items) that specifically gates for honest-limits compliance. Examples:
- Does this claim a number? Is the number current and verifiable?
- Does this use any word from the "Words to Avoid" list?
- Does this describe coverage without stating known limits?
- Would a skeptical SOC analyst find a claim they could disprove in 5 minutes?

---

## Marketing Site

### 9. Build a real homepage
**Issue:** The site homepage appears to be an empty gradient. The brand system hasn't been tested against real web layouts yet.
**Action:** Design and build a homepage that puts the palette, typography, voice, and logo together on a real page. This will surface any remaining disconnects between the documented system and practical execution. The sales pitch content is strong enough to be the starting copy.

---

## Priority Order

| Priority | Item | Why |
|----------|------|-----|
| 1 | #8 Honest-limits gate | Protects your biggest differentiator before more content ships |
| 2 | #6 Consolidate worktree docs | Low effort, high impact on team alignment |
| 3 | #2 Logo/palette alignment | Visual inconsistency compounds over time |
| 4 | #4 Brand foundation | Strategic anchor for all future decisions |
| 5 | #1 Logo metaphor test | Informs whether a redesign is needed before scaling |
| 6 | #9 Homepage | Forces the system to work as a whole |
| 7 | #7 Dashboard direction | Can evolve, but the decision should be conscious |
| 8 | #3 Wordmark documentation | Quick documentation task |
| 9 | #5 Logo usage guidelines | Becomes urgent when others start using the mark |
