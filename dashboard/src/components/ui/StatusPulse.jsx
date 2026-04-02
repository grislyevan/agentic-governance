/**
 * StatusPulse — Real-time status indicator.
 *
 * Unified status system for the command center:
 *   - live: green pulse (data < 30s old)
 *   - stale: amber steady (data > 60s old)
 *   - error: red pulse (API failure)
 *   - offline: gray (disconnected)
 *
 * Props:
 *   status  - 'live' | 'stale' | 'error' | 'offline'
 *   label   - optional text label next to indicator
 *   size    - 'sm' | 'md' (default 'sm')
 */

const STATUS_CONFIG = {
  live: {
    dot: 'bg-detec-healthy',
    pulse: true,
    label: 'Live',
    ringClass: 'ring-detec-healthy/30',
  },
  stale: {
    dot: 'bg-detec-stale',
    pulse: false,
    label: 'Stale',
    ringClass: '',
  },
  error: {
    dot: 'bg-detec-critical',
    pulse: true,
    label: 'Error',
    ringClass: 'ring-detec-critical/30',
  },
  offline: {
    dot: 'bg-detec-ink-disabled',
    pulse: false,
    label: 'Offline',
    ringClass: '',
  },
};

const SIZES = {
  sm: { dot: 'w-1.5 h-1.5', ring: 'w-3 h-3', text: 'text-data-xs' },
  md: { dot: 'w-2 h-2', ring: 'w-4 h-4', text: 'text-data-sm' },
};

export default function StatusPulse({ status = 'offline', label, size = 'sm' }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.offline;
  const sz = SIZES[size] || SIZES.sm;
  const displayLabel = label ?? cfg.label;

  return (
    <span className="inline-flex items-center gap-1.5" title={displayLabel}>
      <span className="relative inline-flex items-center justify-center">
        {/* Pulse ring */}
        {cfg.pulse && (
          <span
            className={`absolute ${sz.ring} rounded-full ${cfg.dot} opacity-40 motion-safe:animate-ping`}
            aria-hidden="true"
          />
        )}
        {/* Dot */}
        <span className={`relative ${sz.dot} rounded-full ${cfg.dot}`} />
      </span>
      {displayLabel && (
        <span className={`font-data ${sz.text} text-detec-ink-secondary`}>{displayLabel}</span>
      )}
    </span>
  );
}
