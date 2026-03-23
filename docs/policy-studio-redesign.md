# Policy Studio Redesign — Layout and API Spec

Single source of truth for the Light Enterprise Dashboard and Policy Studio: pixel-level layout, interaction behavior, and API contracts. Used by frontend implementation and backend follow-up.

---

## Global visual spec

### Page canvas

- **Background:** `#f8f9fb` (detec-ui-page)
- **Max content width:** 1440px
- **Horizontal padding:** desktop 32px, large desktop 40px
- **Vertical page padding:** 24px

### Typography

- **Primary text:** `#111827` (detec-ui-text)
- **Secondary text:** `#6b7280` (detec-ui-muted / textSecondary)
- **Scale:**
  - Page title: 28px / semibold
  - Section title: 20px / semibold
  - Card title: 16px / semibold
  - Field label: 13px / medium
  - Body text: 14px
  - Helper text: 12px

### Surface treatment

- **Card background:** white (`#ffffff`, detec-ui-surface)
- **Border:** 1px solid `#e5e7eb` (detec-ui-border)
- **Radius:** 10px, 12px, 14px (rounded-detec, rounded-detec-md, rounded-detec-lg)
- **Shadow:**
  - Default cards: `0 1px 3px rgba(0,0,0,.08)` (shadow-detec-sm)
  - Elevated: `0 4px 12px rgba(0,0,0,.06)` (shadow-detec-card)

### Inputs

- **Height:** 40px
- **Radius:** 10px
- **Border:** #e5e7eb
- **Background:** white
- **Padding:** 0 12px
- **Focus:** subtle blue outer ring (no neon/glow)
- **Textarea min-height:** 96px

### Buttons

- **Primary:** blue background, white text, 40px height, 16px horizontal padding
- **Secondary:** white background, gray border, dark text
- **Tertiary:** transparent, muted text
- **Focus:** no glowing states

---

## Policy Studio page layout

Use a full page, not a small modal.

### Desktop layout

- Two-column shell:
  - **Main content:** `minmax(0, 1fr)`
  - **Right rail:** 320px
- **Column gap:** 24px

### Vertical structure

1. Page header
2. Stepper row
3. Main content + right rail
4. Sticky footer actions

### Header

- **Container:** full width inside content max, margin bottom 20px
- **Left:** Title "New Policy", subtitle one sentence
- **Right:** Cancel, Save draft (optional close icon if modal/drawer exists)
- **Spacing:** title to subtitle 4px, header to stepper 20px

### Stepper

- **Container:** white card, height 64px, padding 0 20px, radius 12px, border + shadow
- **Layout:** horizontal step items, equal spacing; each step: number/icon left, label right, connector between steps
- **States:**
  - Inactive: label #9ca3af, connector #e5e7eb
  - Active: label #111827, indicator blue fill or ring, bottom accent
  - Complete: blue or muted success, no neon
- **Labels:** Basics, Source, Scope, Rules, Review

### Main content card

- White background, radius 12px, border, shadow
- **Padding:** 24px
- **Min height:** 560px
- **Section rhythm:** section title margin bottom 16px, field group gap 16px, major section gap 24px

### Right rail

- **Width:** 320px
- **Card stack:** gap 16px; cards: Help, Example, Live summary
- **Card padding:** 16px
- **Content:** title 14px semibold, body 13px regular; tag/chip style for selected values
- **Behavior:** rail visible for all steps; summary updates immediately; help and examples change per step

### Step-specific layout

- **Step 1 (Basics):** Two-column grid (2fr / 1fr), gap 16px; full-width fields; two-column row for Severity + Outcome; status collapsed or de-emphasized.
- **Step 2 (Source):** Section title "Where should this policy look?"; source cards grid 2 columns, card height 96px, padding 16px, radius 12px; selected: blue border, subtle blue tint, check mark; "Future connectors" section with divider, lighter treatment.
- **Step 3 (Scope):** Top block "What are you trying to protect or govern?"; stacked groups (Data at risk, Activity types, Sensitivity); chip groups or selectable cards; selected chips: soft blue background, blue border.
- **Step 4 (Rules):** Title + helper; right-side toggle Simple / Advanced; intent template row; simple mode stacked rule blocks; advanced mode large editor, monospace JSON, inline validation.
- **Step 5 (Review):** Single-column summary; sections Basics, Source, Scope, Rules, Enforcement, Explainability, Preview; each section bordered block with edit link; explainability as bullets (signals, conditions, outcome, session linkage); preview disabled or stubbed.

### Footer action bar

- **Placement:** sticky bottom, white background, top border, subtle shadow upward, padding 16px 24px
- **Left:** Cancel
- **Right:** Save draft; on steps 1–4 also Continue; on step 5: Preview matches, Submit for review, Publish
- **Buttons:** 40px height min, 12px gap between buttons

---

## Interaction behavior

- **Navigation:** Continue validates current step only; Back never discards data; leaving page with unsaved changes prompts confirmation.
- **Validation:** Inline beneath field; red for error text and border; no aggressive error banners unless submit fails.
- **Draft:** Save draft from any step; toast top-right or bottom-right; saved draft remains unpublished.
- **Mode switch (Rules):** Simple to Advanced: confirm if generated structure will be converted. Advanced to Simple: only if structure is compatible, else show explanation.

---

## Forward API contract (D2)

**Current** (no backend change for v1): Policies API accepts `rule_id`, `rule_version`, `description`, `is_active`, `parameters` (JSON). Create/update only; no `category` in request body.

**Desired long-term** (for backend migration):

| Field | Type | Notes |
|-------|------|--------|
| name | string | Display name (may differ from rule_id) |
| description | string | Short description |
| goal | string | Policy goal |
| lifecycle_status | string | draft, submitted, approved, published |
| severity | string | low, medium, high, critical |
| enforcement_action | string | detect, warn, approval_required, block |
| scope | object/array | Scope definition |
| source | object/array | Source/connector definition |
| rule_definition | object | Conditions, precedence, etc. |
| created_by | string | User/tenant |
| approved_by | string | Optional |
| created_at | datetime | |
| updated_at | datetime | |

Spec clearly separates temporary compatibility (current payload) from this desired model so backend can plan migration.

---

## Preview matches strategy (D3)

- **V1 options:** Disabled with "Coming soon"; or stub using sample events; or real endpoint if implemented.
- **Recommendation:** Ship stubbed or disabled in v1 unless a real API is straightforward.
- **Acceptance:** Button behavior and copy are honest; no fake promise of live preview if backend does not support it.
