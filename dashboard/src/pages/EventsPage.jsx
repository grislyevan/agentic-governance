import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchEvents, blockEventOnce, createPolicyFromEvent } from '../lib/api';
import useAuth from '../hooks/useAuth';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';

const PAGE_SIZE = 50;

const MITRE_TECHNIQUES = [
  'T1005', 'T1059', 'T1059.004', 'T1071', 'T1071.001', 'T1074', 'T1074.001',
  'T1098', 'T1119', 'T1204', 'T1204.002', 'T1543', 'T1547', 'T1552', 'T1555',
  'T1565', 'T1565.001', 'T1567', 'T1567.001', 'T1537',
];

const DECISION_COLORS = {
  allow: 'bg-detec-teal-500/15 text-detec-teal-500',
  block: 'bg-detec-enforce-block/15 text-detec-enforce-block',
  approval_required: 'bg-amber-500/15 text-amber-400',
  detect: 'bg-detec-ui-accent/10 text-detec-ui-accent',
};

function DecisionBadge({ state }) {
  if (!state) return <span className="text-detec-ui-muted text-xs">-</span>;
  const colors = DECISION_COLORS[state] || 'bg-detec-slate-200 text-detec-ui-muted';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${colors}`}>
      {state}
    </span>
  );
}

function ConfidenceMeter({ value }) {
  if (value == null) return <span className="text-detec-ui-muted text-xs">-</span>;
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? 'bg-detec-teal-500' :
    pct >= 50 ? 'bg-amber-400' :
    'bg-detec-slate-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-12 h-1.5 bg-detec-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-detec-ui-muted tabular-nums">{pct}%</span>
    </div>
  );
}

function MitreBadges({ techniques }) {
  if (!techniques || techniques.length === 0) return <span className="text-detec-ui-muted text-xs">-</span>;
  const ids = techniques.map(t => t.subtechnique || t.technique_id);
  return (
    <div className="flex flex-wrap gap-1">
      {ids.slice(0, 4).map(id => (
        <span key={id} className="text-xs px-1.5 py-0.5 rounded font-mono bg-detec-slate-200 text-detec-ui-text">
          {id}
        </span>
      ))}
      {ids.length > 4 && (
        <span className="text-xs text-detec-ui-muted">+{ids.length - 4}</span>
      )}
    </div>
  );
}

function SeverityBadge({ level }) {
  if (!level) return null;
  const colors = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-amber-400',
    low: 'text-detec-ui-muted',
    info: 'text-detec-ui-muted',
  };
  return (
    <span className={`text-xs font-medium ${colors[level] || 'text-detec-ui-muted'}`}>
      {level}
    </span>
  );
}

function BlockModal({ event, onClose, onBlockOneTime, onCreatePolicy }) {
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState(null);

  const handleOneTime = async () => {
    setError(null);
    setLoading('one_time');
    try {
      await onBlockOneTime(event.id);
      onClose();
    } catch (e) {
      setError(e.message || 'Block request failed');
    } finally {
      setLoading(null);
    }
  };

  const handleCreatePolicy = async () => {
    setError(null);
    setLoading('policy');
    try {
      await onCreatePolicy(event.id);
      onClose();
    } catch (e) {
      setError(e.message || 'Create policy failed');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-detec-ui-surface border border-detec-ui-border rounded-xl shadow-xl max-w-md w-full p-5">
        <h3 className="text-lg font-semibold text-detec-ui-text mb-2">Block this detection</h3>
        <p className="text-sm text-detec-ui-muted mb-4">
          Choose how to block: one time only for this event, or create a policy so similar detections are blocked from now on.
        </p>
        {error && (
          <div className="mb-4 rounded-lg bg-red-900/30 border border-red-700/50 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={handleOneTime}
            disabled={!!loading}
            className="w-full rounded-lg bg-detec-slate-200 hover:bg-detec-slate-200 text-detec-ui-text px-4 py-3 text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {loading === 'one_time' ? 'Blocking...' : 'Block one time only'}
          </button>
          <button
            type="button"
            onClick={handleCreatePolicy}
            disabled={!!loading}
            className="w-full rounded-lg bg-detec-enforce-block/20 hover:bg-detec-enforce-block/30 text-detec-enforce-block border border-detec-enforce-block/40 px-4 py-3 text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {loading === 'policy' ? 'Creating policy...' : 'Create policy (block moving forward)'}
          </button>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full text-sm text-detec-ui-muted hover:text-detec-ui-text"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function EventDetailPanel({ event, onClose, canManage, onBlockSuccess }) {
  const [showBlockModal, setShowBlockModal] = useState(false);
  const navigate = useNavigate();

  const handleBlockOneTime = async (eventId) => {
    await blockEventOnce(eventId);
    onBlockSuccess?.();
  };

  const handleCreatePolicy = async (eventId) => {
    const policy = await createPolicyFromEvent(eventId);
    onBlockSuccess?.();
    navigate('/policies');
  };

  if (!event) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full sm:max-w-md lg:max-w-lg h-full bg-detec-ui-page border-l border-detec-ui-border overflow-y-auto">
        <div className="sticky top-0 bg-detec-ui-page border-b border-detec-ui-border px-5 py-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-detec-ui-text">Event Detail</h2>
          <div className="flex items-center gap-2">
            {canManage && event.decision_state !== 'block' && (
              <button
                type="button"
                onClick={() => setShowBlockModal(true)}
                className="rounded-lg bg-detec-enforce-block/20 hover:bg-detec-enforce-block/30 text-detec-enforce-block border border-detec-enforce-block/40 px-3 py-1.5 text-xs font-medium transition-colors"
              >
                Block
              </button>
            )}
            <button onClick={onClose} className="text-detec-ui-muted hover:text-detec-ui-text">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <div className="p-5 space-y-4">
          <Row label="Event ID" value={event.event_id} mono />
          <Row label="Type" value={event.event_type} />
          <Row label="Observed" value={new Date(event.observed_at).toLocaleString()} />
          <Row label="Tool" value={[event.tool_name, event.tool_version].filter(Boolean).join(' ')} />
          <Row label="Tool Class" value={event.tool_class} />
          <Row label="Decision" value={event.decision_state}>
            <DecisionBadge state={event.decision_state} />
          </Row>
          <Row label="Rule ID" value={event.rule_id} mono />
          <Row label="Severity" value={event.severity_level}>
            <SeverityBadge level={event.severity_level} />
          </Row>
          <Row label="Confidence" value={event.attribution_confidence}>
            <ConfidenceMeter value={event.attribution_confidence} />
          </Row>
          {event.signature_verified != null && (
            <Row label="Signature" value={event.signature_verified ? 'Verified' : 'Not verified'} />
          )}
          {event.payload?.agent_status && (
            <div>
              <div className="text-xs text-detec-ui-muted uppercase tracking-wider font-medium mb-2">Agent status</div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs bg-detec-ui-surface/80 border border-detec-ui-border/50 rounded-lg p-3">
                {event.payload.agent_status.uptime_seconds != null && (
                  <><dt className="text-detec-ui-muted">Uptime (s)</dt><dd className="text-detec-ui-text font-mono">{event.payload.agent_status.uptime_seconds}</dd></>
                )}
                {event.payload.agent_status.scans_per_minute != null && (
                  <><dt className="text-detec-ui-muted">Scans/min</dt><dd className="text-detec-ui-text font-mono">{event.payload.agent_status.scans_per_minute}</dd></>
                )}
                {event.payload.agent_status.avg_scan_ms != null && (
                  <><dt className="text-detec-ui-muted">Avg scan (ms)</dt><dd className="text-detec-ui-text font-mono">{event.payload.agent_status.avg_scan_ms}</dd></>
                )}
                {event.payload.agent_status.trees_per_scan != null && (
                  <><dt className="text-detec-ui-muted">Trees/scan</dt><dd className="text-detec-ui-text font-mono">{event.payload.agent_status.trees_per_scan}</dd></>
                )}
                {event.payload.agent_status.provider != null && (
                  <><dt className="text-detec-ui-muted">Provider</dt><dd className="text-detec-ui-text">{event.payload.agent_status.provider}</dd></>
                )}
              </dl>
            </div>
          )}
          <div>
            <div className="text-xs text-detec-ui-muted uppercase tracking-wider font-medium mb-2">Full Payload</div>
            <pre className="text-xs text-detec-ui-muted font-mono bg-detec-ui-surface/80 border border-detec-ui-border/50 rounded-lg p-3 overflow-x-auto max-h-96">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>
        </div>
      </div>
      {showBlockModal && (
        <BlockModal
          event={event}
          onClose={() => setShowBlockModal(false)}
          onBlockOneTime={handleBlockOneTime}
          onCreatePolicy={handleCreatePolicy}
        />
      )}
    </div>
  );
}

function Row({ label, value, mono, children }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-xs text-detec-ui-muted w-24 shrink-0 pt-0.5">{label}</span>
      {children || (
        <span className={`text-sm text-detec-ui-text ${mono ? 'font-mono text-xs' : ''}`}>
          {value || <span className="text-detec-ui-muted">-</span>}
        </span>
      )}
    </div>
  );
}

export default function EventsPage({ searchQuery }) {
  const { user } = useAuth();
  const canManage = user?.role === 'owner' || user?.role === 'admin';

  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const [decisionFilter, setDecisionFilter] = useState('');
  const [toolFilter, setToolFilter] = useState('');
  const [mitreFilter, setMitreFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const prevSearch = useRef(searchQuery);

  useEffect(() => {
    if (searchQuery !== prevSearch.current) {
      setPage(1);
      prevSearch.current = searchQuery;
    }
  }, [searchQuery]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const opts = { page, pageSize: PAGE_SIZE };
      if (decisionFilter) opts.decisionState = decisionFilter;
      if (toolFilter) opts.toolName = toolFilter;
      if (mitreFilter) opts.mitreTechnique = mitreFilter;
      if (searchQuery) opts.search = searchQuery;
      const data = await fetchEvents(undefined, opts);
      setEvents(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, decisionFilter, toolFilter, mitreFilter, searchQuery]);

  useEffect(() => { load(); }, [load]);

  const { lastUpdated, paused, togglePause } = usePolling(load);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <h1 className="text-xl sm:text-2xl font-bold text-detec-ui-text">Events</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        {loading && <ApertureSpinner size="sm" label="Loading events" />}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={decisionFilter}
          onChange={e => { setDecisionFilter(e.target.value); setPage(1); }}
          className="bg-detec-ui-surface border border-detec-ui-border rounded-lg px-3 py-3 sm:py-1.5 text-xs text-detec-ui-text focus:outline-none focus:border-detec-ui-accent/50 min-h-[44px] sm:min-h-0"
        >
          <option value="">All decisions</option>
          <option value="allow">Allow</option>
          <option value="block">Block</option>
          <option value="approval_required">Approval Required</option>
          <option value="detect">Detect</option>
        </select>

        <input
          type="text"
          value={toolFilter}
          onChange={e => { setToolFilter(e.target.value); setPage(1); }}
          placeholder="Filter by tool name"
          className="bg-detec-ui-surface border border-detec-ui-border rounded-lg px-3 py-3 sm:py-1.5 text-xs text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 w-full sm:w-44 min-h-[44px] sm:min-h-0"
        />

        <select
          value={mitreFilter}
          onChange={e => { setMitreFilter(e.target.value); setPage(1); }}
          className="bg-detec-ui-surface border border-detec-ui-border rounded-lg px-3 py-3 sm:py-1.5 text-xs text-detec-ui-text focus:outline-none focus:border-detec-ui-accent/50 min-h-[44px] sm:min-h-0"
        >
          <option value="">All MITRE techniques</option>
          {MITRE_TECHNIQUES.map(tid => (
            <option key={tid} value={tid}>{tid}</option>
          ))}
        </select>

        {(decisionFilter || toolFilter || mitreFilter) && (
          <button
            onClick={() => { setDecisionFilter(''); setToolFilter(''); setMitreFilter(''); setPage(1); }}
            className="text-xs text-detec-ui-muted hover:text-detec-ui-text"
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto text-xs text-detec-ui-muted tabular-nums">
          {total.toLocaleString()} event{total !== 1 ? 's' : ''}
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          <p>{error}</p>
          <p className="text-detec-ui-muted mt-1 text-xs">Check the connection and try again.</p>
        </div>
      )}

      {!loading && !error && (
        <div className="rounded-xl border border-detec-ui-border/50 overflow-x-auto overflow-hidden">
          <table className="w-full text-left min-w-[640px]" aria-label="Detection events">
            <thead>
              <tr className="bg-detec-ui-surface/80 border-b border-detec-ui-border/50">
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Time</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Type</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider hidden md:table-cell">Tool</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider hidden lg:table-cell">Class</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Decision</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Confidence</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider hidden lg:table-cell">MITRE ATT&amp;CK</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ui-muted uppercase tracking-wider hidden md:table-cell">Severity</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center">
                    <p className="text-detec-ui-muted text-sm font-medium">
                      {decisionFilter || toolFilter || mitreFilter || searchQuery ? 'No matching events' : 'No events yet'}
                    </p>
                    <p className="text-detec-ui-muted text-xs mt-1 max-w-sm mx-auto">
                      {decisionFilter || toolFilter || mitreFilter || searchQuery
                        ? 'Try adjusting your filters or search query.'
                        : 'Agent activity will appear here once endpoints are sending events.'}
                    </p>
                  </td>
                </tr>
              ) : events.map((ev) => (
                <tr
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  className="border-b border-detec-ui-border/40 hover:bg-detec-ui-surface/40 cursor-pointer"
                >
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-ui-muted whitespace-nowrap tabular-nums">
                    {new Date(ev.observed_at).toLocaleString()}
                  </td>
                  <td className="px-3 sm:px-4 py-3">
                    <span className="text-xs font-mono text-detec-ui-text">{ev.event_type}</span>
                  </td>
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-ui-text font-medium hidden md:table-cell">
                    {ev.tool_name || <span className="text-detec-ui-muted">-</span>}
                  </td>
                  <td className="px-3 sm:px-4 py-3 hidden lg:table-cell">
                    <span className="text-xs font-mono text-detec-ui-muted">{ev.tool_class || '-'}</span>
                  </td>
                  <td className="px-3 sm:px-4 py-3">
                    <DecisionBadge state={ev.decision_state} />
                  </td>
                  <td className="px-3 sm:px-4 py-3">
                    <ConfidenceMeter value={ev.attribution_confidence} />
                  </td>
                  <td className="px-3 sm:px-4 py-3 hidden lg:table-cell">
                    <MitreBadges techniques={ev.payload?.mitre_attack?.techniques} />
                  </td>
                  <td className="px-3 sm:px-4 py-3 hidden md:table-cell">
                    <SeverityBadge level={ev.severity_level} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-4 py-3 sm:py-1.5 text-sm text-detec-ui-muted hover:text-detec-ui-text disabled:opacity-30 disabled:cursor-not-allowed min-h-[44px] sm:min-h-0"
          >
            Previous
          </button>
          <span className="text-sm text-detec-ui-muted tabular-nums">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages}
            className="px-4 py-3 sm:py-1.5 text-sm text-detec-ui-muted hover:text-detec-ui-text disabled:opacity-30 disabled:cursor-not-allowed min-h-[44px] sm:min-h-0"
          >
            Next
          </button>
        </div>
      )}

      <EventDetailPanel
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        canManage={canManage}
        onBlockSuccess={() => { load(); setSelectedEvent(null); }}
      />
    </div>
  );
}

function PulseIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
