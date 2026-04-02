/**
 * ConfidenceEvidenceStack — 5-layer weighted evidence display.
 *
 * Shows WHY a detection is confident across evidence layers:
 *   L1 Process Tree    ████████░░  0.82
 *   L2 File Activity   ██████░░░░  0.61
 *   L3 Network         █████████░  0.91
 *   L4 Behavioral      ███████░░░  0.73
 *   L5 Scanner Match   ██████████  0.95
 *   ─────────────────────────────
 *      Composite        ████████░░  0.84 HIGH
 *
 * Props:
 *   layers     - array of { name, score } OR just a composite score
 *   composite  - number 0-1 (overall confidence)
 *   sources    - string like "process,file,network" (attribution_sources from event model)
 *   compact    - boolean for inline display
 */

import { useMemo } from 'react';

/* ── Layer definitions (the 5 evidence layers from Detec's scoring architecture) ── */

const LAYER_DEFS = [
  { key: 'process',    label: 'Process Tree',  shortLabel: 'L1 Process',  index: 1 },
  { key: 'file',       label: 'File Activity',  shortLabel: 'L2 File',     index: 2 },
  { key: 'network',    label: 'Network',        shortLabel: 'L3 Network',  index: 3 },
  { key: 'behavioral', label: 'Behavioral',     shortLabel: 'L4 Behavior', index: 4 },
  { key: 'scanner',    label: 'Scanner Match',  shortLabel: 'L5 Scanner',  index: 5 },
];

/* ── Confidence band classification ── */

function classifyConfidence(score) {
  if (score == null) return { band: 'unknown', color: 'text-detec-ink-tertiary', barColor: 'bg-detec-ink-disabled', bgColor: 'bg-detec-ink-disabled/20' };
  if (score >= 0.75) return { band: 'HIGH', color: 'text-detec-confidence-high', barColor: 'bg-detec-confidence-high', bgColor: 'bg-detec-confidence-high/15' };
  if (score >= 0.45) return { band: 'MEDIUM', color: 'text-detec-confidence-medium', barColor: 'bg-detec-confidence-medium', bgColor: 'bg-detec-confidence-medium/15' };
  return { band: 'LOW', color: 'text-detec-confidence-low', barColor: 'bg-detec-confidence-low', bgColor: 'bg-detec-confidence-low/15' };
}

/* ── Build layers from various input formats ── */

function buildLayers(layers, sources, composite) {
  // If explicit layers provided, use them directly
  if (layers && Array.isArray(layers) && layers.length > 0) {
    return layers.map((l, i) => ({
      ...LAYER_DEFS[i] || { key: l.name || `layer-${i}`, label: l.name || `Layer ${i + 1}`, shortLabel: l.name || `L${i + 1}`, index: i + 1 },
      score: l.score,
      active: l.score != null && l.score > 0,
    }));
  }

  // If sources string provided (e.g., "process,file,network"), show which layers contributed
  if (sources) {
    const sourceList = typeof sources === 'string'
      ? sources.split(',').map(s => s.trim().toLowerCase())
      : Array.isArray(sources) ? sources.map(s => s.toLowerCase()) : [];

    return LAYER_DEFS.map(def => ({
      ...def,
      score: sourceList.includes(def.key) ? (composite || 0.5) : null,
      active: sourceList.includes(def.key),
    }));
  }

  // Fallback: show all layers with composite score
  if (composite != null) {
    return LAYER_DEFS.map(def => ({
      ...def,
      score: null,
      active: false,
    }));
  }

  return [];
}

/* ── Evidence bar ── */

function EvidenceBar({ label, score, active, compact }) {
  const cls = classifyConfidence(score);
  const pct = score != null ? Math.round(score * 100) : 0;

  if (compact) {
    return (
      <div className="flex items-center gap-1.5" title={`${label}: ${score != null ? pct + '%' : 'N/A'}`}>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? cls.barColor : 'bg-detec-ink-disabled'}`} />
        <span className="text-data-xs font-data text-detec-ink-tertiary w-14 truncate">{label}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 h-6">
      {/* Layer label */}
      <span className="text-data-xs font-data text-detec-ink-secondary w-24 shrink-0 text-right truncate">
        {label}
      </span>

      {/* Bar track */}
      <div className="flex-1 h-2 rounded-full bg-detec-edge-subtle overflow-hidden min-w-[80px] max-w-[200px]">
        {active && score != null && (
          <div
            className={`h-full rounded-full ${cls.barColor} transition-all duration-300`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>

      {/* Score value */}
      <span className={`text-data-sm font-data w-10 text-right shrink-0 tabular-nums ${active ? cls.color : 'text-detec-ink-disabled'}`}>
        {active && score != null ? score.toFixed(2) : '—'}
      </span>
    </div>
  );
}

/* ── Main component ── */

export default function ConfidenceEvidenceStack({ layers, composite, sources, compact = false }) {
  const builtLayers = useMemo(() => buildLayers(layers, sources, composite), [layers, sources, composite]);
  const compositeCls = classifyConfidence(composite);

  if (builtLayers.length === 0 && composite == null) {
    return (
      <p className="text-data-sm font-data text-detec-ink-tertiary">No confidence data</p>
    );
  }

  /* ── Compact: inline badge with dot indicators ── */
  if (compact) {
    return (
      <div className="inline-flex items-center gap-2">
        {composite != null && (
          <span className={`text-data-sm font-data font-medium tabular-nums ${compositeCls.color}`}>
            {(composite * 100).toFixed(0)}%
          </span>
        )}
        <span className={`text-data-xs font-data font-medium px-1.5 py-0.5 rounded-detec ${compositeCls.bgColor} ${compositeCls.color}`}>
          {compositeCls.band}
        </span>
        {builtLayers.length > 0 && (
          <div className="flex items-center gap-0.5 ml-1">
            {builtLayers.map(l => (
              <span
                key={l.key}
                className={`w-1.5 h-1.5 rounded-full ${l.active ? classifyConfidence(l.score).barColor : 'bg-detec-ink-disabled'}`}
                title={`${l.label}: ${l.active && l.score != null ? (l.score * 100).toFixed(0) + '%' : 'N/A'}`}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  /* ── Full: vertical stack with bars ── */
  return (
    <div className="space-y-1" role="group" aria-label="Confidence evidence layers">
      {/* Layer bars */}
      {builtLayers.map(l => (
        <EvidenceBar
          key={l.key}
          label={l.shortLabel}
          score={l.score}
          active={l.active}
        />
      ))}

      {/* Divider */}
      {composite != null && (
        <>
          <div className="border-t border-detec-edge my-1.5" />

          {/* Composite row */}
          <div className="flex items-center gap-3 h-7">
            <span className="text-data-sm font-data font-medium text-detec-ink-primary w-24 shrink-0 text-right">
              Composite
            </span>
            <div className="flex-1 h-2.5 rounded-full bg-detec-edge-subtle overflow-hidden min-w-[80px] max-w-[200px]">
              <div
                className={`h-full rounded-full ${compositeCls.barColor} transition-all duration-300`}
                style={{ width: `${Math.round(composite * 100)}%` }}
              />
            </div>
            <span className={`text-data-sm font-data font-bold tabular-nums w-10 text-right shrink-0 ${compositeCls.color}`}>
              {composite.toFixed(2)}
            </span>
            <span className={`text-data-xs font-data font-medium px-1.5 py-0.5 rounded-detec ${compositeCls.bgColor} ${compositeCls.color} shrink-0`}>
              {compositeCls.band}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
