import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchEvents } from '../lib/api';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';

const PAGE_SIZE = 50;

const DECISION_COLORS = {
  allow: 'bg-detec-teal-500/15 text-detec-teal-500',
  block: 'bg-detec-enforce-block/15 text-detec-enforce-block',
  approval_required: 'bg-amber-500/15 text-amber-400',
  detect: 'bg-detec-primary-500/15 text-detec-primary-400',
};

function DecisionBadge({ state }) {
  if (!state) return <span className="text-detec-slate-600 text-xs">-</span>;
  const colors = DECISION_COLORS[state] || 'bg-detec-slate-700 text-detec-slate-400';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${colors}`}>
      {state}
    </span>
  );
}

function ConfidenceMeter({ value }) {
  if (value == null) return <span className="text-detec-slate-600 text-xs">-</span>;
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? 'bg-detec-teal-500' :
    pct >= 50 ? 'bg-amber-400' :
    'bg-detec-slate-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-12 h-1.5 bg-detec-slate-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-detec-slate-400 tabular-nums">{pct}%</span>
    </div>
  );
}

function SeverityBadge({ level }) {
  if (!level) return null;
  const colors = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-amber-400',
    low: 'text-detec-slate-400',
    info: 'text-detec-slate-500',
  };
  return (
    <span className={`text-xs font-medium ${colors[level] || 'text-detec-slate-400'}`}>
      {level}
    </span>
  );
}

function EventDetailPanel({ event, onClose }) {
  if (!event) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-lg h-full bg-detec-slate-900 border-l border-detec-slate-700 overflow-y-auto">
        <div className="sticky top-0 bg-detec-slate-900 border-b border-detec-slate-700 px-5 py-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-detec-slate-200">Event Detail</h2>
          <button onClick={onClose} className="text-detec-slate-500 hover:text-detec-slate-300">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
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
          <div>
            <div className="text-xs text-detec-slate-500 uppercase tracking-wider font-medium mb-2">Full Payload</div>
            <pre className="text-xs text-detec-slate-400 font-mono bg-detec-slate-800/50 border border-detec-slate-700/50 rounded-lg p-3 overflow-x-auto max-h-96">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono, children }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-xs text-detec-slate-500 w-24 shrink-0 pt-0.5">{label}</span>
      {children || (
        <span className={`text-sm text-detec-slate-200 ${mono ? 'font-mono text-xs' : ''}`}>
          {value || <span className="text-detec-slate-600">-</span>}
        </span>
      )}
    </div>
  );
}

export default function EventsPage({ searchQuery }) {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const [decisionFilter, setDecisionFilter] = useState('');
  const [toolFilter, setToolFilter] = useState('');
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
      if (searchQuery) opts.search = searchQuery;
      const data = await fetchEvents(undefined, opts);
      setEvents(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, decisionFilter, toolFilter, searchQuery]);

  useEffect(() => { load(); }, [load]);

  const { lastUpdated, paused, togglePause } = usePolling(load);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-detec-slate-100">Events</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        {loading && <ApertureSpinner size="sm" label="Loading events" />}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={decisionFilter}
          onChange={e => { setDecisionFilter(e.target.value); setPage(1); }}
          className="bg-detec-slate-800 border border-detec-slate-700 rounded-lg px-3 py-1.5 text-xs text-detec-slate-300 focus:outline-none focus:border-detec-primary-500/50"
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
          className="bg-detec-slate-800 border border-detec-slate-700 rounded-lg px-3 py-1.5 text-xs text-detec-slate-300 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 w-44"
        />

        {(decisionFilter || toolFilter) && (
          <button
            onClick={() => { setDecisionFilter(''); setToolFilter(''); setPage(1); }}
            className="text-xs text-detec-slate-500 hover:text-detec-slate-300"
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto text-xs text-detec-slate-500 tabular-nums">
          {total.toLocaleString()} event{total !== 1 ? 's' : ''}
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      {events.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
          <div className="text-3xl mb-3 opacity-40">
            <PulseIcon />
          </div>
          <div className="text-detec-slate-400 text-sm font-medium mb-1">
            {decisionFilter || toolFilter || searchQuery ? 'No matching events' : 'No events yet'}
          </div>
          <div className="text-detec-slate-600 text-sm max-w-sm mx-auto">
            {decisionFilter || toolFilter || searchQuery
              ? 'Try adjusting your filters or search query.'
              : 'Detection, policy, and enforcement events will appear here as endpoints report in. Connect an agent to get started.'}
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="rounded-xl border border-detec-slate-700/50 overflow-hidden">
          <table className="w-full text-left" aria-label="Detection events">
            <thead>
              <tr className="bg-detec-slate-800/80 border-b border-detec-slate-700/50">
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Type</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Class</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Decision</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Confidence</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Severity</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  className="border-b border-detec-slate-700/40 hover:bg-detec-slate-800/40 cursor-pointer"
                >
                  <td className="px-4 py-3 text-sm text-detec-slate-400 whitespace-nowrap tabular-nums">
                    {new Date(ev.observed_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-mono text-detec-slate-300">{ev.event_type}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-slate-200 font-medium">
                    {ev.tool_name || <span className="text-detec-slate-600">-</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-mono text-detec-slate-400">{ev.tool_class || '-'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <DecisionBadge state={ev.decision_state} />
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceMeter value={ev.attribution_confidence} />
                  </td>
                  <td className="px-4 py-3">
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
            className="px-3 py-1.5 text-sm text-detec-slate-400 hover:text-detec-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-detec-slate-500 tabular-nums">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-sm text-detec-slate-400 hover:text-detec-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}

      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
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
