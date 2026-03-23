# Detec — Typography

Font families, weights, and hierarchy for UI, marketing, and collateral.

---

## Font Families

### IBM Plex Sans — Primary

Used for all UI text, headings, body copy, and marketing materials. Chosen for its clean geometry, strong legibility at small sizes, and modern-but-not-trendy character. Free, open-source, and available via Google Fonts.

**Load from Google Fonts:**
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

**Tailwind config:**
```js
fontFamily: {
  sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
}
```

### IBM Plex Mono — Code / Technical

Used for code snippets, confidence scores, rule IDs, file paths, CLI output, and any technical content where monospace is expected. Pairs with IBM Plex Sans as part of the same type superfamily.

**Load from Google Fonts:**
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
```

**Tailwind config:**
```js
fontFamily: {
  mono: ['"IBM Plex Mono"', 'monospace'],
}
```

---

## Weight Scale

| Weight | CSS Value | Use |
|---|---|---|
| Regular | `400` | Body text, descriptions, table cells |
| Medium | `500` | Labels, navigation items, secondary headings, badge text |
| Semibold | `600` | Section headings, card titles, emphasis in body text |
| Bold | `700` | Page titles, the "Detec" wordmark, primary CTAs |

Do not use weights outside this set (no 100/200/300/800/900). Four weights is enough to establish hierarchy without visual noise.

---

## Size Scale (Dashboard UI)

Based on Tailwind's default scale. Sizes are in `rem` relative to a `16px` root.

| Token | Size | Line Height | Use |
|---|---|---|---|
| `text-xs` | 0.75rem (12px) | 1rem | Timestamps, badges, muted metadata |
| `text-sm` | 0.875rem (14px) | 1.25rem | Table cells, sidebar nav, secondary labels |
| `text-base` | 1rem (16px) | 1.5rem | Body text, form inputs, descriptions |
| `text-lg` | 1.125rem (18px) | 1.75rem | Card titles, section headings |
| `text-xl` | 1.25rem (20px) | 1.75rem | Page section titles |
| `text-2xl` | 1.5rem (24px) | 2rem | Page titles |

---

## Heading Hierarchy

| Level | Size | Weight | Color (dark mode) | Example |
|---|---|---|---|---|
| Page title | `text-2xl` | Bold (700) | `slate-100` | "Endpoints" |
| Section heading | `text-lg` | Semibold (600) | `slate-100` | "Active Tools" |
| Card title | `text-sm` | Semibold (600) | `slate-200` | "Confidence Breakdown" |
| Label | `text-sm` | Medium (500) | `slate-400` | "Last Seen" |
| Body | `text-sm` | Regular (400) | `slate-300` | Description text |
| Muted / caption | `text-xs` | Regular (400) | `slate-500` | "Updated 2 min ago" |

---

## Monospace Usage

Use `font-mono` (IBM Plex Mono) for:

- Confidence scores: `0.87`
- Rule IDs: `ENFORCE-003`
- Tool class labels: `Class C`
- File paths: `~/.claude/settings.json`
- CLI commands and output
- JSON/code snippets
- API endpoints: `POST /events`

Do not use monospace for general UI text, headings, or navigation.

---

## Letter Spacing

| Context | Tracking | Tailwind Class |
|---|---|---|
| Wordmark ("Detec") | Tight | `tracking-tight` |
| Page titles | Tight | `tracking-tight` |
| Body text | Normal | (default) |
| All-caps labels (if used) | Wide | `tracking-wide` |

Avoid all-caps for anything longer than 2–3 words. Use sparingly for badge labels or status indicators.

---

## Marketing / Collateral

For non-UI contexts (one-sheets, pitch decks, print), use the same font families:

| Element | Font | Weight | Size Guidance |
|---|---|---|---|
| Headline | IBM Plex Sans | Bold (700) | 28–36pt |
| Subheadline | IBM Plex Sans | Semibold (600) | 18–22pt |
| Body copy | IBM Plex Sans | Regular (400) | 11–13pt |
| Pull quotes / callouts | IBM Plex Sans | Medium (500) | 14–16pt |
| Code / technical detail | IBM Plex Mono | Regular (400) | 10–11pt |

---

## File Reference

| File | What it does |
|---|---|
| `dashboard/index.html` | Loads IBM Plex Sans (400/500/600) and IBM Plex Mono (400/500) from Google Fonts |
| `dashboard/tailwind.config.cjs` | Maps `font-sans` and `font-mono` to the Plex families |
| `branding/brand-foundation.md` | References this file in the brand document index |
