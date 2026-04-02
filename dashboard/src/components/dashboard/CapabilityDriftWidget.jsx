/**
 * CapabilityDriftWidget — shows capability drift signals from agent telemetry.
 *
 * Data source:
 *   There is no dedicated drift REST endpoint. The `detec_agent_capability_drift_total`
 *   Prometheus counter is updated server-side whenever an event payload includes
 *   `agent_status.capability_drift[]`. The list of drifted capabilities is carried
 *   inside session reports under `evasion_vectors` (which includes "capability_drift"
 *   as a vector ID) and in raw event payloads under `agent_status.capability_drift`.
 *
 *   Strategy: fetch the most recent session reports (GET /api/session-reports) and
 *   look for any report whose `evasion_vectors` contains "capability_drift". Each
 *   matching report represents a drifting endpoint. Aggregate by endpoint_id so one
 *   row appears per endpoint, with severity derived from how many sessions drifted.
 *
 *   Fallback: if no session reports exist, query GET /api/events with event_type
 *   filtering isn't supported server-side for agent_status events, so we stay with
 *   session reports only and show "No drift detected" when none match.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchSessionReports } from '../../lib/api';

// ── Severity derivation ───────────────────────────────────────────────────────

/** Derive severity from drift session count per endpoint. */
function deriveSeverity(count) {
  if (count >= 3) return 'High';
  if (count >= 2) return 'Medium';
  return 'Low';
}

const SEVERITY_BADGE = {
  Low:    'bg-blue-500/15 text-blue-400 border-blue-500/30',
  Medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  High:   'bg-red-500/15 text-red-400 border-red-500/30',
};

function SeverityBadge({ level }) {
  const cls = SEVERITY_BADGE[level] || SEVERITY_BADGE.Low;
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border ${cls}`}>
      {level}
    </span>
  );
}

// ── Aggregation ───────────────────────────────────────────────────────────────

/**
 * Aggregate session reports into per-endpoint drift rows.
 * A session contributes if its evasion_vectors includes "capability_drift".
 */
function aggregateDrift(reports) {
  const byEndpoint = new Map();

  for (const report of reports) {
    const vectors = report.evasion_vectors || [];
    if (!vectors.includes('capability_drift')) continue;

    const endpointId = report.endpoint_id || 'unknown';
    const tool = report.tool || 'unknown';
    const sessionId = report.session_report_id;

    if (!byEndpoint.has(endpointId)) {
      byEndpoint.set(endpointId, {
        endpointId,
        tool,
        sessionCount: 0,
        latestSessionId: sessionId,
        latestAt: report.started_at,
      });
    }
    const entry = byEndpoint.get(endpointId);
    entry.sessionCount += 1;

    // Keep latest session reference
    if (report.started_at && entry.latestAt) {
      if (new Date(report.started_at) > new Date(entry.latestAt)) {
        entry.latestAt = report.started_at;
        entry.latestSessionId = sessionId;
        entry.tool = tool;
      }
    }
  }

  return Array.from(byEndpoint.values()).map((e) => ({
    ...e,
    severity: deriveSeverity(e.sessionCount),
  }));
}

// ── Timestamp helper ──────────────────────────────────────────────────────────

function relativeTime(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Widget ────────────────────────────────────────────────────────────────────

export default function CapabilityDriftWidget({ onNavigate }) {
  const [driftRows, setDriftRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [checkedAt, setCheckedAt] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch the 100 most recent session reports; drift events are infrequent
      // so this window is sufficient for operator review.
      const data = await fetchSessionReports({}, { limit: 100 });
      const reports = Array.isArray(data) ? data : (data.items || []);
      const rows = aggregateDrift(reports);
      setDriftRows(rows);
      setCheckedAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || 'Failed to load drift data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="rounded-xl border border-detec-slate-700 bg-detec-slate-800 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <DriftIcon />
          <h2 className="text-sm font-semibold text-detec-ui-text">Capability Drift</h2>
        </div>
        <div className="flex items-center gap-3">
          {checkedAt && (
            <span className="text-xs text-detec-ui-muted" title={checkedAt}>
              Checked {relativeTime(checkedAt)}
            </span>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="text-xs text-detec-ui-accent hover:underline disabled:opacity-40 transition-opacity"
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-detec-ui-muted">
          <span className="inline-block w-3 h-3 border-2 border-detec-ui-border border-t-detec-ui-accent rounded-full animate-spin" />
          Loading drift data…
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-lg border border-detec-enforce-block/20 bg-detec-enforce-block/5 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      {/* No drift */}
      {!loading && !error && driftRows.length === 0 && (
        <div className="flex items-center gap-2.5 rounded-lg border border-detec-teal-500/30 bg-detec-teal-500/10 px-4 py-3">
          <GreenCheckIcon />
          <span className="text-sm font-medium text-detec-teal-500">No drift detected</span>
        </div>
      )}

      {/* Drift rows */}
      {!loading && !error && driftRows.length > 0 && (
        <div className="space-y-2">
          {driftRows.map((row) => (
            <div
              key={row.endpointId}
              className="rounded-lg border border-detec-slate-700 bg-detec-slate-900 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3"
            >
              {/* Endpoint + tool info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-detec-ui-text truncate max-w-[200px]" title={row.endpointId}>
                    {row.endpointId}
                  </span>
                  <SeverityBadge level={row.severity} />
                </div>
                <p className="text-xs text-detec-ui-muted mt-0.5">
                  Tool: <span className="text-detec-ui-text">{row.tool}</span>
                  {' · '}
                  {row.sessionCount} session{row.sessionCount !== 1 ? 's' : ''} with drift
                  {row.latestAt && ` · last ${relativeTime(row.latestAt)}`}
                </p>
                <p className="text-xs text-detec-ui-muted mt-0.5">
                  Capability disappeared from agent telemetry (capability_drift vector)
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3 shrink-0">
                <a
                  href="https://github.com/grislyevan/agentic-governance/blob/main/docs/capability-drift-runbook.md"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-detec-primary-500 hover:underline"
                >
                  View runbook
                </a>
                {onNavigate && (
                  <button
                    type="button"
                    onClick={() => onNavigate('sessions', { endpointId: row.endpointId })}
                    className="rounded border border-detec-slate-700 px-3 py-1 text-xs font-medium text-detec-slate-200 bg-detec-slate-700 hover:bg-detec-slate-600 transition-colors"
                  >
                    View endpoint
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DriftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function GreenCheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
