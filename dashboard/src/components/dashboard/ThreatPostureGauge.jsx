/**
 * ThreatPostureGauge — SVG ring gauge showing proportional enforcement breakdown.
 * Replaces SummaryCards as the hero metric for the SOC command center dashboard.
 */

const ENFORCE_COLORS = {
  block:             '#dc2626',
  approval_required: '#ea580c',
  warn:              '#d97706',
  detect:            '#2563eb',
};

const SEGMENTS = [
  { key: 'block',             label: 'Blocked',           color: ENFORCE_COLORS.block },
  { key: 'approval_required', label: 'Approval Required', color: ENFORCE_COLORS.approval_required },
  { key: 'warn',              label: 'Warned',            color: ENFORCE_COLORS.warn },
  { key: 'detect',            label: 'Detected',          color: ENFORCE_COLORS.detect },
];

const RING_SIZE    = 120;
const STROKE_WIDTH = 12;
const RADIUS       = (RING_SIZE - STROKE_WIDTH) / 2;   // 54
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;             // ~339.29
const GAP_PX       = 2;
const EMPTY_COLOR  = '#334155'; // slate-700, neutral gray for zero-state

export default function ThreatPostureGauge({ counts, onSegmentClick }) {
  const total = SEGMENTS.reduce((sum, s) => sum + (counts[s.key] ?? 0), 0);
  const allZero = total === 0;

  // Build ring segment data: dasharray + dashoffset for each arc
  const ringSegments = buildRingSegments(counts, total);

  return (
    <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-5">
      <div className="flex items-center gap-6">
        {/* Left: SVG donut ring */}
        <div className="shrink-0">
          <svg
            width={RING_SIZE}
            height={RING_SIZE}
            viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}
            aria-label={`Enforcement breakdown: ${total} total detections`}
            role="img"
          >
            <g transform={`rotate(-90 ${RING_SIZE / 2} ${RING_SIZE / 2})`}>
              {allZero ? (
                <circle
                  cx={RING_SIZE / 2}
                  cy={RING_SIZE / 2}
                  r={RADIUS}
                  fill="none"
                  stroke={EMPTY_COLOR}
                  strokeWidth={STROKE_WIDTH}
                />
              ) : (
                ringSegments.map((seg) => (
                  <circle
                    key={seg.key}
                    cx={RING_SIZE / 2}
                    cy={RING_SIZE / 2}
                    r={RADIUS}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth={STROKE_WIDTH}
                    strokeDasharray={`${seg.dashLength} ${CIRCUMFERENCE - seg.dashLength}`}
                    strokeDashoffset={-seg.offset}
                    strokeLinecap="butt"
                    style={{ transition: 'stroke-dasharray 0.3s ease, stroke-dashoffset 0.3s ease' }}
                  />
                ))
              )}
            </g>

            {/* Center label */}
            <text
              x={RING_SIZE / 2}
              y={RING_SIZE / 2 - 4}
              textAnchor="middle"
              dominantBaseline="central"
              className="font-data"
              style={{ fontSize: '24px', fontWeight: 700, fill: 'var(--color-detec-ink-primary, #f1f5f9)' }}
            >
              {total}
            </text>
            <text
              x={RING_SIZE / 2}
              y={RING_SIZE / 2 + 16}
              textAnchor="middle"
              dominantBaseline="central"
              style={{ fontSize: '10px', fill: 'var(--color-detec-ink-tertiary, #64748b)' }}
            >
              detections
            </text>
          </svg>
        </div>

        {/* Right: Stat rows */}
        <div className="flex-1 min-w-0 -my-1">
          {SEGMENTS.map((seg) => {
            const value = counts[seg.key] ?? 0;

            return (
              <button
                key={seg.key}
                type="button"
                onClick={() => onSegmentClick?.(seg.key)}
                className="w-full flex items-center justify-between gap-3 px-2.5 py-1.5 rounded-detec text-left transition-colors hover:bg-detec-raised cursor-pointer"
              >
                <span className="flex items-center gap-2.5 min-w-0">
                  <span
                    className="shrink-0 w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: seg.color }}
                    aria-hidden="true"
                  />
                  <span className="text-sm text-detec-ink-secondary truncate">
                    {seg.label}
                  </span>
                </span>
                <span className="font-data text-sm font-medium text-detec-ink-primary tabular-nums">
                  {value}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}


/**
 * Build an array of { key, color, dashLength, offset } for SVG stroke-dasharray ring.
 * Segments are drawn clockwise from 12-o'clock.
 * Each segment is reduced by GAP_PX to create visual spacing.
 */
function buildRingSegments(counts, total) {
  if (total === 0) return [];

  const activeSegments = SEGMENTS.filter((s) => (counts[s.key] ?? 0) > 0);
  const segmentCount = activeSegments.length;

  // Total gap space to distribute
  const totalGap = segmentCount * GAP_PX;
  const usableCircumference = CIRCUMFERENCE - totalGap;

  let offset = 0;
  return activeSegments.map((seg) => {
    const value = counts[seg.key] ?? 0;
    const proportion = value / total;
    const dashLength = proportion * usableCircumference;
    const result = {
      key: seg.key,
      color: seg.color,
      dashLength,
      offset,
    };
    // Advance offset by this segment's arc + gap
    offset += dashLength + GAP_PX;
    return result;
  });
}
