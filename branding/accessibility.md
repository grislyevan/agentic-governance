# Detec — Color Accessibility

WCAG 2.1 contrast audit for all brand color combinations used in the UI and collateral.

**Standard:** WCAG 2.1 AA requires 4.5:1 for normal text, 3.0:1 for large text (18px+ or 14px+ bold). AAA requires 7.0:1 / 4.5:1.

---

## Text on Surfaces

All core text combinations pass AA or better.

| Combination | Ratio | Grade |
|---|---|---|
| slate-100 on slate-900 (primary text, dark mode) | 16.30 | AAA |
| slate-400 on slate-900 (secondary text, dark mode) | 6.96 | AA |
| slate-500 on slate-900 (muted text, dark mode) | 3.75 | AA-large |
| slate-100 on slate-800 (text on card, dark mode) | 13.35 | AAA |
| slate-400 on slate-800 (secondary on card, dark mode) | 5.71 | AA |
| slate-200 on slate-950 (sidebar text) | 16.36 | AAA |
| slate-400 on slate-950 (sidebar secondary) | 7.87 | AAA |
| slate-900 on slate-50 (primary text, light mode) | 17.06 | AAA |
| slate-600 on slate-50 (secondary text, light mode) | 7.24 | AAA |
| slate-900 on white (text on card, light mode) | 17.85 | AAA |
| slate-600 on white (secondary on card, light mode) | 7.58 | AAA |

**Note:** slate-500 on slate-900 (3.75) passes AA for large text only. Use for muted timestamps, captions, and disabled states — not for body text.

---

## Enforcement Ladder — Dark Mode

Used as badge/pill text or icon color on the dark dashboard background.

| State | Color on slate-900 | Ratio | Grade |
|---|---|---|---|
| Detect | indigo-500 `#6366f1` | 4.00 | AA-large |
| Warn | amber-500 `#f59e0b` | 8.31 | AAA |
| Approval | orange-500 `#f97316` | 6.37 | AA |
| Block | red-500 `#ef4444` | 4.74 | AA |

**Issue:** Detect (indigo-500 on slate-900) at 4.00 is below AA for normal text. It passes for large text and for non-text UI elements (icons, badges, borders).

**Recommendation:** Use indigo-400 (`#818cf8`, 5.98 ratio, AA) for small enforcement labels if needed. Keep indigo-500 for badges, icons, and larger text.

---

## Enforcement Ladder — Light Mode

Used as text or badge color on tinted pill backgrounds.

| State | Color on tinted bg | Ratio | Grade | Fix |
|---|---|---|---|---|
| Detect | indigo-500 on indigo-50 | 3.99 | AA-large | Use indigo-600 (`#4f46e5`) → 5.62 AA |
| Warn | amber-500 on amber-50 | **2.07** | **FAIL** | Use amber-700 (`#b45309`) → 4.84 AA |
| Approval | orange-500 on orange-50 | **2.64** | **FAIL** | Use orange-700 (`#c2410c`) → 4.88 AA |
| Block | red-500 on red-50 | 3.44 | AA-large | Acceptable for badges; use red-600 for text |

**On white backgrounds:**

| State | Color on white | Ratio | Grade | Fix |
|---|---|---|---|---|
| Detect | indigo-500 | 4.47 | AA-large | Use indigo-600 → 6.29 AA |
| Warn | amber-500 | **2.15** | **FAIL** | Use amber-700 (`#b45309`) → 5.02 AA |
| Approval | orange-500 | **2.80** | **FAIL** | Use orange-700 (`#c2410c`) → 5.18 AA |
| Block | red-500 | 3.76 | AA-large | Use red-600 for small text |

### Implementation Rule

When enforcement colors appear as text on light backgrounds, step down to the 700 weight for amber and orange, 600 for indigo and red. The 500 values remain the canonical brand colors for dark-mode usage, icons, and non-text elements (borders, chart fills, badge backgrounds with white text).

---

## Confidence Bands — Dark Mode

| Band | Color on slate-900 | Ratio | Grade |
|---|---|---|---|
| High | teal-500 `#14b8a6` | 7.17 | AAA |
| Medium | amber-500 `#f59e0b` | 8.31 | AAA |
| Low | slate-400 `#94a3b8` | 6.96 | AA |

All confidence band colors pass AA on dark backgrounds.

---

## Interactive Elements

| Combination | Ratio | Grade |
|---|---|---|
| White on indigo-500 (primary button) | 4.47 | AA-large |
| White on indigo-600 (button hover/active) | 6.29 | AA |
| indigo-400 on slate-900 (active nav) | 5.98 | AA |

**Recommendation:** Primary buttons using indigo-500 with white text pass AA for large text (14px bold / 18px regular). For smaller button text, use indigo-600 as the button background.

---

## Summary of Required Fixes

| Where | Current | Fix to | Ratio improves |
|---|---|---|---|
| Amber text on light surfaces | amber-500 | amber-700 (`#b45309`) | 2.15 → 5.02 |
| Orange text on light surfaces | orange-500 | orange-700 (`#c2410c`) | 2.80 → 5.18 |
| Indigo text on light surfaces | indigo-500 | indigo-600 (`#4f46e5`) | 4.47 → 6.29 |
| Small text primary buttons | indigo-500 bg | indigo-600 bg (`#4f46e5`) | 4.47 → 6.29 |

These fixes apply only to **text on light backgrounds**. On dark backgrounds (slate-900/800/950), the 500-weight values all pass AA or better and should remain unchanged.

---

## Accessible Color Pairs Quick Reference

For developers — use these pairs for guaranteed AA compliance:

```
Dark mode (slate-900 bg):
  Primary text:     slate-100  (#f1f5f9)  — 16.30 AAA
  Secondary text:   slate-400  (#94a3b8)  —  6.96 AA
  Muted/disabled:   slate-500  (#64748b)  —  3.75 AA-large only
  Accent text:      indigo-400 (#818cf8)  —  5.98 AA
  Success/detect:   teal-500   (#14b8a6)  —  7.17 AAA
  Warning:          amber-500  (#f59e0b)  —  8.31 AAA

Light mode (white/slate-50 bg):
  Primary text:     slate-900  (#0f172a)  — 17.85 AAA
  Secondary text:   slate-600  (#475569)  —  7.58 AAA
  Detect label:     indigo-600 (#4f46e5)  —  6.29 AA
  Warn label:       amber-700  (#b45309)  —  5.02 AA
  Approval label:   orange-700 (#c2410c)  —  5.18 AA
  Block label:      red-500    (#ef4444)  —  3.76 AA-large
```
