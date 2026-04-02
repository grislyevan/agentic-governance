/**
 * Detec — Tailwind CSS Color Tokens
 *
 * Command-center design system. Near-black surfaces, threat-spectrum
 * enforcement colors, borders-only depth. Every token earns its place.
 *
 * Usage: spread into your tailwind.config.js theme.extend.colors
 */

module.exports = {
  detec: {
    /* ── Surface elevation (near-black, no blue cast) ── */
    void:    '#06080d',   // canvas / page background
    ground:  '#0c1017',   // sidebar, panels
    surface: '#121820',   // cards, content areas
    raised:  '#1a2232',   // dropdowns, popovers
    overlay: '#222d3d',   // modals, toasts

    /* ── Text hierarchy ── */
    ink: {
      primary:   '#e8ecf2',  // headings, primary content
      secondary: '#8b95a8',  // supporting text, labels
      tertiary:  '#5a6478',  // metadata, timestamps
      disabled:  '#3a4252',  // disabled, placeholder
    },

    /* ── Border progression (use with rgba in components) ── */
    // Preferred: rgba(255,255,255, 0.04/0.08/0.14/0.22)
    // Fallback hex for static contexts:
    edge: {
      subtle:   '#ffffff0a',  // ~4% white — card edges, soft separation
      DEFAULT:  '#ffffff14',  // ~8% white — standard borders
      emphasis: '#ffffff24',  // ~14% white — hover, active elements
      strong:   '#ffffff38',  // ~22% white — focus rings, critical boundaries
    },

    /* ── Enforcement spectrum (threat colors) ── */
    enforce: {
      block:      '#dc2626',  // crimson — critical / block
      blockBg:    '#dc262619', // 10% opacity background
      approval:   '#ea580c',  // orange — approval required
      approvalBg: '#ea580c19',
      warn:       '#d97706',  // amber — warning
      warnBg:     '#d9770619',
      detect:     '#2563eb',  // cold blue — informational / detect
      detectBg:   '#2563eb19',
    },

    /* ── Confidence bands ── */
    confidence: {
      high:   '#0d9488',  // teal
      medium: '#d97706',  // amber
      low:    '#64748b',  // slate
    },

    /* ── Semantic ── */
    healthy:  '#16a34a',  // phosphor green — compliant, active, success
    stale:    '#d97706',  // amber — needs attention
    critical: '#dc2626',  // crimson — critical, error

    /* ── Brand accent ── */
    brand: {
      DEFAULT: '#3b82f6',  // blue-500 — links, interactive
      hover:   '#60a5fa',  // blue-400
      muted:   '#3b82f619', // 10% background
    },

    /* ── Control tokens (inputs, buttons) ── */
    control: {
      bg:     '#0a0e15',  // input backgrounds (inset, darker than surface)
      border: '#ffffff14', // input borders (matches edge.DEFAULT)
      focus:  '#3b82f6',  // focus ring color (brand blue)
    },

    /* ── Legacy compatibility (maps old tokens → new) ── */
    // Remove these after full migration
    ui: {
      page:    '#06080d',   // → detec-void
      surface: '#121820',   // → detec-surface
      text:    '#e8ecf2',   // → detec-ink-primary
      muted:   '#8b95a8',   // → detec-ink-secondary
      textSecondary: '#8b95a8',
      border:  '#ffffff14', // → detec-edge
      accent:  '#3b82f6',   // → detec-brand
      accentHover: '#60a5fa',
    },
    slate: {
      50:  '#f8fafc',
      100: '#e8ecf2',
      200: '#c8d0de',
      300: '#8b95a8',
      400: '#5a6478',
      500: '#3a4252',
      600: '#222d3d',
      700: '#ffffff14',
      800: '#121820',
      900: '#06080d',
      950: '#030508',
    },
    primary: {
      400: '#60a5fa',
      500: '#3b82f6',
      DEFAULT: '#3b82f6',
    },
    teal: {
      DEFAULT: '#0d9488',
      500: '#0d9488',
    },
    amber: {
      DEFAULT: '#d97706',
      500: '#d97706',
    },
  },
};
