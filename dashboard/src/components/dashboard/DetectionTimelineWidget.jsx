import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { fetchEvents, getApiConfig } from '../../lib/api';

// ── Enforcement decision colors (inline hex for SVG) ────────────────
const DECISION_COLORS = {
  block: '#dc2626',
  approval_required: '#ea580c',
  warn: '#d97706',
  detect: '#2563eb',
};

const DECISION_LABELS = {
  block: 'Block',
  approval_required: 'Approval',
  warn: 'Warn',
  detect: 'Detect',
};

const MS_24H = 24 * 60 * 60 * 1000;

// ── Helpers ──────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return iso;
  }
}

function formatHourLabel(date) {
  return date.toLocaleTimeString([], { hour: 'numeric', hour12: true });
}

/** Return a color for a decision_state, falling back to detect blue. */
function dotColor(state) {
  return DECISION_COLORS[state] || DECISION_COLORS.detect;
}

/** Compute the horizontal % position (0 = left / 24h ago, 100 = right / now). */
function timeToPercent(observedAt, now) {
  const elapsed = now - new Date(observedAt).getTime();
  // Clamp: anything older than 24h sits at 0%, anything in the future sits at 100%
  const pct = (1 - elapsed / MS_24H) * 100;
  return Math.max(0, Math.min(100, pct));
}

/**
 * Group events into time buckets so overlapping dots stack vertically.
 * Each bucket covers ~0.5% of the timeline width (~7 minutes).
 */
function bucketEvents(events, now) {
  const BUCKET_WIDTH = 0.5; // percent
  const buckets = new Map();

  for (const evt of events) {
    const pct = timeToPercent(evt.observed_at, now);
    const key = Math.round(pct / BUCKET_WIDTH);
    if (!buckets.has(key)) {
      buckets.set(key, { pct: key * BUCKET_WIDTH, events: [] });
    }
    buckets.get(key).events.push(evt);
  }

  return Array.from(buckets.values()).sort((a, b) => a.pct - b.pct);
}

// ── 6-hour markers ──────────────────────────────────────────────────

function HourMarkers({ now }) {
  const markers = useMemo(() => {
    const result = [];
    for (let hoursAgo = 24; hoursAgo >= 0; hoursAgo -= 6) {
      const markerTime = new Date(now - hoursAgo * 60 * 60 * 1000);
      const pct = ((24 - hoursAgo) / 24) * 100;
      result.push({ pct, label: hoursAgo === 0 ? 'Now' : formatHourLabel(markerTime) });
    }
    return result;
  }, [now]);

  return (
    <>
      {markers.map((m) => (
        <div
          key={m.pct}
          className="absolute bottom-0 flex flex-col items-center pointer-events-none"
          style={{ left: `${m.pct}%`, transform: 'translateX(-50%)' }}
        >
          <div className="w-px h-3 bg-detec-edge" />
          <span className="font-data text-data-xs text-detec-ink-tertiary mt-0.5 whitespace-nowrap select-none">
            {m.label}
          </span>
        </div>
      ))}
    </>
  );
}

// ── Tooltip ─────────────────────────────────────────────────────────

function Tooltip({ event, anchorRef }) {
  if (!event || !anchorRef) return null;

  const color = dotColor(event.decision_state);

  return (
    <div
      className="absolute z-30 bg-detec-raised border border-detec-edge rounded-detec-md px-2.5 py-1.5 pointer-events-none"
      style={{
        bottom: '100%',
        left: '50%',
        transform: 'translateX(-50%) translateY(-6px)',
        minWidth: '180px',
      }}
    >
      <div className="font-data text-data-sm text-detec-ink-primary space-y-0.5">
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: color }}
          />
          <span className="font-medium" style={{ color }}>
            {DECISION_LABELS[event.decision_state] || event.decision_state}
          </span>
        </div>
        <div className="text-detec-ink-secondary truncate" title={event.tool_name}>
          Tool: {event.tool_name || 'unknown'}
        </div>
        <div className="text-detec-ink-secondary truncate" title={event.rule_id}>
          Rule: {event.rule_id || 'unknown'}
        </div>
        <div className="text-detec-ink-tertiary">
          {formatTime(event.observed_at)}
        </div>
      </div>
    </div>
  );
}

// ── Dot cluster (stacked events at one bucket position) ─────────────

function DotCluster({ bucket, hovered, onHover, onLeave, onClick }) {
  const DOT_SIZE = 6;
  const DOT_GAP = 3;
  const MAX_VISIBLE = 3;

  const visible = bucket.events.slice(0, MAX_VISIBLE);
  const overflow = bucket.events.length - MAX_VISIBLE;

  return (
    <div
      className="absolute"
      style={{
        left: `${bucket.pct}%`,
        bottom: '20px', // above the hour markers
        transform: 'translateX(-50%)',
      }}
    >
      <div className="relative flex flex-col-reverse items-center" style={{ gap: `${DOT_GAP}px` }}>
        {visible.map((evt, i) => {
          const key = `${evt.observed_at}-${evt.tool_name}-${evt.rule_id}-${i}`;
          const isHovered = hovered === key;

          return (
            <div key={key} className="relative">
              {isHovered && <Tooltip event={evt} anchorRef />}
              <svg
                width={DOT_SIZE}
                height={DOT_SIZE}
                viewBox={`0 0 ${DOT_SIZE} ${DOT_SIZE}`}
                className="cursor-pointer transition-transform duration-150 hover:scale-150"
                onMouseEnter={() => onHover(key)}
                onMouseLeave={onLeave}
                onClick={() => onClick(evt)}
                role="button"
                aria-label={`${DECISION_LABELS[evt.decision_state] || evt.decision_state} detection: ${evt.tool_name} at ${formatTime(evt.observed_at)}`}
              >
                <circle
                  cx={DOT_SIZE / 2}
                  cy={DOT_SIZE / 2}
                  r={DOT_SIZE / 2}
                  fill={dotColor(evt.decision_state)}
                />
              </svg>
            </div>
          );
        })}
        {overflow > 0 && (
          <span className="font-data text-data-xs text-detec-ink-tertiary leading-none select-none">
            +{overflow}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Legend ───────────────────────────────────────────────────────────

function Legend() {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {Object.entries(DECISION_LABELS).map(([key, label]) => (
        <div key={key} className="flex items-center gap-1">
          <span
            className="inline-block w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: DECISION_COLORS[key] }}
          />
          <span className="font-data text-data-xs text-detec-ink-tertiary">{label}</span>
        </div>
      ))}
    </div>
  );
}

// ── Empty state ─────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-6 gap-2">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="#16a34a" strokeWidth="1.5" />
        <path d="M8 12l3 3 5-5" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-xs text-detec-ink-secondary">
        No detections in the last 24 hours
      </span>
      <span className="font-data text-data-xs" style={{ color: '#16a34a' }}>
        All clear
      </span>
    </div>
  );
}

// ── Loading skeleton ────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="bg-detec-surface border border-detec-edge rounded-detec-md p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-32 bg-detec-raised rounded animate-pulse" />
        <div className="h-4 w-14 bg-detec-raised rounded animate-pulse" />
      </div>
      <div className="relative h-[60px] bg-detec-raised/30 rounded animate-pulse" />
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────

export default function DetectionTimelineWidget({ onNavigate }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hovered, setHovered] = useState(null);
  const now = useRef(Date.now()).current;

  const loadEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const config = getApiConfig();
      const twentyFourHoursAgo = new Date(now - MS_24H).toISOString();
      const data = await fetchEvents(config, { observedAfter: twentyFourHoursAgo, pageSize: 200 });
      setEvents(data.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load detections');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [now]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const buckets = useMemo(() => bucketEvents(events, now), [events, now]);

  const handleDotClick = useCallback(
    (evt) => {
      onNavigate?.('events');
    },
    [onNavigate],
  );

  const handleHover = useCallback((key) => setHovered(key), []);
  const handleLeave = useCallback(() => setHovered(null), []);

  // ── Loading ──
  if (loading) {
    return <LoadingSkeleton />;
  }

  // ── Error ──
  if (error) {
    return (
      <div className="bg-detec-surface border border-detec-edge rounded-detec-md p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-detec-ink-primary">Detection Timeline</h3>
          <span className="text-xs text-detec-ink-tertiary">Last 24h</span>
        </div>
        <div className="text-xs text-detec-ink-secondary">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#dc2626] mr-1.5 align-middle" />
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-detec-surface border border-detec-edge rounded-detec-md p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-detec-ink-primary">Detection Timeline</h3>
        <span className="text-xs text-detec-ink-tertiary">Last 24h</span>
      </div>

      {events.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Timeline area */}
          <div className="relative w-full" style={{ height: '60px' }}>
            {/* Baseline */}
            <div
              className="absolute left-0 right-0 bg-detec-edge"
              style={{ bottom: '20px', height: '1px' }}
            />

            {/* Hour markers */}
            <HourMarkers now={now} />

            {/* Event dots */}
            {buckets.map((bucket, idx) => (
              <DotCluster
                key={idx}
                bucket={bucket}
                hovered={hovered}
                onHover={handleHover}
                onLeave={handleLeave}
                onClick={handleDotClick}
              />
            ))}
          </div>

          {/* Legend + count */}
          <div className="flex items-center justify-between mt-2">
            <Legend />
            <span className="font-data text-data-xs text-detec-ink-tertiary">
              {events.length} event{events.length !== 1 ? 's' : ''}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
