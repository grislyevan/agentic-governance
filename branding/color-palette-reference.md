# Detec — Color Palette Reference

Quick-reference for design, development, and collateral production.

---

## Brand Palette

### Primary — Soft Indigo
Brand mark, headers, primary actions, navigation.

| Weight | Hex | Use |
|---|---|---|
| 50 | `#eef2ff` | Hover backgrounds, tinted surfaces |
| 100 | `#e0e7ff` | Selected states, light badges |
| 200 | `#c7d2fe` | Focus rings, borders |
| 300 | `#a5b4fc` | Secondary buttons |
| 400 | `#818cf8` | Hover on primary |
| **500** | **`#6366f1`** | **Brand anchor — primary buttons, logos, headings** |
| 600 | `#4f46e5` | Active/pressed states |
| 700 | `#4338ca` | Dark accents |
| 800 | `#3730a3` | Dark mode primary |
| 900 | `#312e81` | Dark mode headings |
| 950 | `#1e1b4b` | Dark mode deep accents |

### Secondary — Teal
Data visualizations, detection indicators, positive/healthy states.

| Weight | Hex | Use |
|---|---|---|
| **500** | **`#14b8a6`** | **Secondary anchor — data viz, success states** |
| 600 | `#0d9488` | Charts, indicators |
| 700 | `#0f766e` | Dark mode secondary |

### Accent — Amber
Attention states, warnings, call-to-action highlights.

| Weight | Hex | Use |
|---|---|---|
| **500** | **`#f59e0b`** | **Accent anchor — warnings, CTAs** |
| 600 | `#d97706` | Active/hover on amber elements |
| 700 | `#b45309` | Dark mode amber |

---

## Enforcement Ladder Colors

These are the most important semantic colors in the product. SOC operators will see them constantly.

| State | Color | Hex | Background (light) | Background (dark) |
|---|---|---|---|---|
| Detect | Soft Indigo | `#6366f1` | `#eef2ff` | `#312e81` |
| Warn | Amber | `#f59e0b` | `#fffbeb` | `#78350f` |
| Approval Required | Orange | `#f97316` | `#fff7ed` | `#7c2d12` |
| Block | Coral Red | `#ef4444` | `#fef2f2` | `#7f1d1d` |

---

## Confidence Band Colors

| Band | Range | Color | Hex |
|---|---|---|---|
| High | >= 0.80 | Teal | `#14b8a6` |
| Medium | 0.50 – 0.79 | Amber | `#f59e0b` |
| Low | < 0.50 | Slate 400 | `#94a3b8` |

---

## Surface Colors

| Surface | Light Mode | Dark Mode |
|---|---|---|
| Page background | `#f8fafc` | `#0f172a` |
| Card / panel | `#ffffff` | `#1e293b` |
| Elevated card | `#ffffff` + shadow | `#334155` |

---

## Text Colors

| Role | Light Mode | Dark Mode |
|---|---|---|
| Primary text | `#0f172a` | `#f1f5f9` |
| Secondary text | `#475569` | `#94a3b8` |
| Muted / disabled | `#94a3b8` | `#475569` |

---

## Design Rationale

- **Soft Indigo** over dark navy: modern and approachable, not corporate/institutional.
- **Teal** over pure cyan: warmer, friendlier, works in both modes.
- **Amber** over yellow: higher contrast, better readability, natural caution association.
- **No neon green / terminal green**: this isn't a threat-hunting war room.
- **No aggressive red dominance**: red is reserved exclusively for Block state.
- Enforcement colors form a natural warm-to-hot gradient (indigo → amber → orange → red) that operators internalize quickly.

---

## File Formats

- **CSS custom properties:** `branding/color-system.css`
- **Tailwind config tokens:** `branding/tailwind-colors.js`
