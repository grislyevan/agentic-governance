# Detec — Logo Usage Guidelines

## Logo Assets

- **Primary logo (horizontal):** `detec-logo-concept-v2.png` — mark + wordmark side by side
- Previous concept: `detec-logo-concept-v1.png` (archived — replaced by v2)
- **Master icon source:** `Icon.icns` — macOS icon container with sizes from 16x16 to 1024x1024. This is the canonical source for all icon generation (web favicons, macOS app icon, PWA icons).
- **Isolated mark (PNG):** `Icon.png` — aperture mark only, high-res PNG (1192x1183)
- **Favicon (.ico):** `detec-icon.ico` — multi-size (16/32/48px), generated from `Icon.icns`
- Monochrome and dark-mode variants: TBD

---

## Logo Components

The Detec logo has two components that can be used together or independently:

### 1. The Mark (aperture icon)

A circular aperture/iris formed by three swirling sections in teal, amber, and indigo that converge on a central focal point. The shape evokes a lens or scanner — signals spiraling inward to produce a single, clear finding.

**Color mapping:**
| Section | Brand Role | Hex |
|---|---|---|
| Top-left (teal) | Secondary — detection, positive states | `#14b8a6` |
| Top-right (amber) | Accent — attention, enforcement | `#f59e0b` |
| Bottom (indigo) | Primary — brand anchor | `#6366f1` |

**Central dot:** The focal point of detection — the moment signals converge into a confident finding.

**Use the mark alone for:**
- App icons and favicons (circular form scales well)
- Social media profile images
- Small-format contexts where the wordmark won't be legible
- Watermarks

### 2. The Wordmark

"Detec" set in a bold, clean sans-serif in deep indigo/navy. The weight and letter spacing are calibrated for legibility at all sizes.

**Use the wordmark alone for:**
- Text-heavy contexts where the mark would be redundant
- Navigation bars where horizontal space is tight
- Monochrome contexts where the three-color mark isn't practical

---

## Preferred Combinations

| Context | Use |
|---|---|
| Website header | Mark + wordmark (horizontal lockup) |
| App icon / favicon | Mark only |
| Marketing collateral / one-sheet | Mark + wordmark (horizontal lockup) |
| Email signature | Mark + wordmark (small horizontal) |
| Social media avatar | Mark only |
| Documentation | Wordmark only |
| Dark backgrounds | Mark + wordmark (use light/white wordmark variant) |

---

## Clear Space

Maintain clear space around the logo equal to the height of the "D" in the wordmark on all sides. No other text, icons, or visual elements should intrude into this space.

---

## Minimum Sizes

| Format | Minimum Width |
|---|---|
| Mark + wordmark (horizontal) | 120px / 1.5in |
| Mark only | 24px / 0.3in |
| Wordmark only | 80px / 1in |

Below these sizes, the logo loses legibility and should not be used.

---

## Color Contexts

### On light backgrounds (white, light gray)
Use the full-color mark with the deep indigo/navy wordmark as shown in the primary logo.

### On dark backgrounds (slate 900, black)
Use the full-color mark with a white or slate-100 (`#f1f5f9`) wordmark. The three-color mark retains its vibrancy on dark backgrounds.

### Monochrome
When color printing isn't available, use an all-indigo (`#6366f1`) or all-white version of the complete logo (mark + wordmark). Do not use the three-color mark in monochrome — use the solid single-color mark instead.

---

## Don'ts

- Don't rotate or skew the logo
- Don't change the colors of the three shapes in the mark
- Don't add drop shadows, outlines, or effects
- Don't place the logo on busy photographic backgrounds without a solid backing
- Don't stretch or distort the aspect ratio
- Don't rearrange the mark and wordmark (e.g., don't stack them vertically unless a stacked lockup is formally designed)
- Don't use the three-color gradient mark at sizes below 24px — switch to the solid monochrome mark

---

## Iteration Notes (v2)

v2 resolved the play-button read from v1 by switching to an aperture/iris motif. Remaining items:

1. **Fourth color** — a light blue appears between the teal and indigo sections, possibly from gradient blending. Decide whether to keep it or tighten to the three canonical brand colors.
2. **Monochrome version** — the overlapping curves need to maintain visual separation without color. Produce and test a solid single-color version.
3. **Wordmark color** (`~#2d2b7a`) is darker than the brand primary (`#6366f1`). Decide whether the wordmark should match the primary or maintain the darker navy for contrast/legibility.
4. **Stacked variant** (mark above wordmark) should be designed for square contexts.
5. **Animated variant** — the swirling aperture opening/closing could make a compelling loading animation for the dashboard.

---

## File Reference

| File | Description |
|---|---|
| **`Icon.icns`** | **Master icon source** — macOS icon container, 16px to 1024px. All other icons are derived from this. |
| `Icon.png` | Isolated aperture mark, high-res PNG (1192x1183) |
| `detec-logo-concept-v2.png` | Primary horizontal lockup, full color, light background (current) |
| `Logo-N-I.png` | Logo variant (name + icon) |
| `Detec_Logo_300.png` | Logo at 300px |
| `Agent-V1.png` | Agent illustration concept v1 |
| `detec-icon.ico` | Multi-size favicon (16/32/48px), generated from `Icon.icns` |
| `detec-logo-concept-v1.png` | Archived — D-letterform concept, replaced due to play-button read |

All web and app icons are generated from `Icon.icns`. To regenerate after updating the master: run `python packaging/macos/generate-icons.py` for macOS app assets, or the Pillow extraction script for web assets (see commit history).

### Dashboard Icon Assets (`dashboard/public/`)

| File | Size | Purpose |
|---|---|---|
| `favicon.ico` | 16/32/48px | Browser tab icon (legacy format) |
| `favicon.svg` | scalable | Browser tab icon (modern browsers) |
| `favicon-16x16.png` | 16x16 | Small favicon PNG fallback |
| `favicon-32x32.png` | 32x32 | Standard favicon PNG |
| `apple-touch-icon.png` | 180x180 | iOS home screen / Safari |
| `icon-192.png` | 192x192 | PWA manifest icon |
| `icon-512.png` | 512x512 | PWA manifest icon (high-res) |
