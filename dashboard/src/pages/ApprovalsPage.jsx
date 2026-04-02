import { useState, useCallback, useEffect, useRef } from 'react';
import { fetchApprovals, approveRequest, denyRequest, getApprovalStreamUrl } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import ApiErrorBanner from '../components/ui/ApiErrorBanner';
import SectionTabBar from '../components/ui/SectionTabBar';
import ExceptionsPage from './ExceptionsPage';

const TABS = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'denied', label: 'Denied' },
];

function statusBadgeClass(status) {
  if (status === 'pending') return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  if (status === 'approved') return 'bg-green-500/10 text-green-400 border-green-500/30';
  if (status === 'denied') return 'bg-red-500/10 text-red-400 border-red-500/30';
  return 'bg-detec-slate-100 text-detec-ink-primary border-detec-ui-border/50';
}

function statusLabel(status) {
  if (status === 'pending') return 'Pending';
  if (status === 'approved') return 'Approved';
  if (status === 'denied') return 'Denied';
  return status || '';
}

function fmtPct(score) {
  if (score == null) return '—';
  const n = parseFloat(score);
  if (isNaN(n)) return String(score);
  return `${(n * 100).toFixed(1)}%`;
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString();
}

function formatAge(isoString) {
  if (!isoString) return '—';
  const ts = new Date(isoString).getTime();
  if (isNaN(ts)) return '—';
  const diffMs = Date.now() - ts;
  const diffMin = Math.floor(Math.max(0, diffMs) / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const hours = Math.floor(diffMin / 60);
  if (hours < 24) return `${hours}h ${diffMin % 60}m ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function EmptyState({ tab }) {
  const msgs = {
    pending: { title: 'No pending approvals', body: 'When tool executions require human approval, they will appear here.' },
    approved: { title: 'No approved requests', body: 'Requests you have approved will show here.' },
    denied: { title: 'No denied requests', body: 'Requests you have denied will show here.' },
  };
  const m = msgs[tab] || { title: 'Nothing here', body: '' };
  return (
    <div className="rounded-detec-md border border-dashed border-detec-ui-border bg-detec-slate-50 px-8 py-20 text-center">
      <div className="mb-3 opacity-40">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <div className="text-detec-ink-secondary text-sm font-medium mb-1">{m.title}</div>
      <div className="text-detec-ink-secondary text-sm max-w-sm mx-auto">{m.body}</div>
    </div>
  );
}

function ActionModal({ item, mode, onConfirm, onCancel, loading }) {
  const [reason, setReason] = useState('');
  const isApprove = mode === 'approve';
  const reasonRequired = !isApprove;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (reasonRequired && !reason.trim()) return;
    onConfirm(reason.trim() || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="rounded-detec-md border border-detec-ui-border/50 bg-detec-void/95 p-6 max-w-md w-full mx-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-detec-ink-primary mb-1">
          {isApprove ? 'Approve request' : 'Deny request'}
        </h2>
        <p className="text-sm text-detec-ink-secondary mb-4">
          Tool: <span className="font-mono text-detec-ink-primary">{item.tool_name}</span>
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary uppercase tracking-wider mb-1">
              Reason {reasonRequired ? <span className="text-red-400">*</span> : <span className="text-detec-ink-secondary">(optional)</span>}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required={reasonRequired}
              rows={3}
              placeholder={isApprove ? 'Reason for approval (optional)' : 'Reason for denial (required)'}
              className="w-full px-3 py-2 rounded-detec-md border border-detec-ui-border/50 bg-detec-surface text-detec-ink-primary text-sm resize-none focus:outline-none focus:ring-2 focus:ring-detec-brand/30 focus:border-detec-brand"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1.5 text-sm text-detec-ink-secondary hover:text-detec-ink-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || (reasonRequired && !reason.trim())}
              className={`px-4 py-1.5 text-sm font-medium rounded-detec-md disabled:opacity-50 transition-colors ${
                isApprove
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
            >
              {loading ? 'Saving...' : isApprove ? 'Approve' : 'Deny'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DetailDrawer({ item, onClose, onAction, actionLoading, onNavigate }) {
  const [mode, setMode] = useState(null); // 'approve' | 'deny' | null

  if (!item) return null;

  const handleConfirm = (reason) => {
    onAction(item, mode, reason);
    setMode(null);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 z-40 w-full max-w-md bg-detec-surface border-l border-detec-ui-border shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-detec-ui-border">
          <div className="flex items-center gap-3 min-w-0 flex-wrap">
            <span className="font-mono font-semibold text-detec-ink-primary truncate">{item.tool_name}</span>
            <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${statusBadgeClass(item.status)}`}>
              {statusLabel(item.status)}
            </span>
            {item.status === 'pending' && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-semibold"
                title="In active posture, the process is suspended (SIGSTOP). In passive/audit posture, this is advisory only."
              >
                Approval requested
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-detec-ink-secondary hover:text-detec-ink-primary transition-colors rounded"
            aria-label="Close detail panel"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Detection */}
          <section>
            <h3 className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider mb-2">Detection</h3>
            <dl className="space-y-1.5">
              <DrawerRow label="Confidence band" value={item.confidence_band || '—'} />
              <DrawerRow label="Confidence score" value={fmtPct(item.confidence_score)} />
              <DrawerRow label="Policy rule" value={item.policy_rule_id ? <span className="font-mono text-xs">{item.policy_rule_id}</span> : '—'} />
              <DrawerRow
                label="Event ID"
                value={
                  item.event_id
                    ? (
                      <button
                        onClick={() => { onClose(); onNavigate?.('events'); }}
                        className="font-mono text-xs text-detec-brand hover:underline"
                      >
                        {item.event_id.slice(0, 16)}…
                      </button>
                    )
                    : '—'
                }
              />
            </dl>
          </section>

          {/* Context */}
          <section>
            <h3 className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider mb-2">Context</h3>
            <dl className="space-y-1.5">
              <DrawerRow label="Endpoint" value={item.endpoint_id ? <span className="font-mono text-xs">{item.endpoint_id.slice(0, 16)}…</span> : '—'} />
              <DrawerRow label="Requester type" value={item.requester_type || '—'} />
              <DrawerRow label="Requested at" value={fmtDate(item.requested_at)} />
            </dl>
          </section>

          {/* Decision */}
          {(item.decided_by || item.decided_at || item.reason) && (
            <section>
              <h3 className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider mb-2">Decision</h3>
              <dl className="space-y-1.5">
                {item.decided_by && <DrawerRow label="Decided by" value={item.decided_by} />}
                {item.decided_at && <DrawerRow label="Decided at" value={fmtDate(item.decided_at)} />}
                {item.reason && <DrawerRow label="Reason" value={item.reason} />}
              </dl>
            </section>
          )}
        </div>

        {/* Actions for pending */}
        {item.status === 'pending' && (
          <div className="px-5 py-4 border-t border-detec-ui-border flex gap-2">
            <button
              onClick={() => setMode('approve')}
              disabled={actionLoading}
              className="flex-1 px-4 py-2 text-sm font-medium rounded-detec-md bg-green-600 hover:bg-green-700 text-white disabled:opacity-50 transition-colors"
            >
              Approve
            </button>
            <button
              onClick={() => setMode('deny')}
              disabled={actionLoading}
              className="flex-1 px-4 py-2 text-sm font-medium rounded-detec-md bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors"
            >
              Deny
            </button>
          </div>
        )}
      </div>

      {mode && (
        <ActionModal
          item={item}
          mode={mode}
          onConfirm={handleConfirm}
          onCancel={() => setMode(null)}
          loading={actionLoading}
        />
      )}
    </>
  );
}

function DrawerRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-4 text-sm">
      <dt className="text-detec-ink-secondary shrink-0 w-32">{label}</dt>
      <dd className="text-detec-ink-primary text-right">{value}</dd>
    </div>
  );
}

const REASON_TEMPLATES = {
  approve: ['Approved by security review', 'Expected behavior for this tool', 'Temporary allow for maintenance'],
  deny: ['Violates security policy', 'Unauthorized tool usage', 'Exceeds approved scope'],
};

export default function ApprovalsPage({ onNavigate }) {
  const [activeTab, setActiveTab] = useState(() => localStorage.getItem('approvals_status_filter') || 'pending');
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  const [sectionTab, setSectionTab] = useState('queue');

  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkDecision, setBulkDecision] = useState(null); // 'approve' | 'deny' | null
  const [bulkReason, setBulkReason] = useState('');
  const [bulkBusy, setBulkBusy] = useState(false);
  const [streamStatus, setStreamStatus] = useState('connecting'); // 'connecting' | 'live' | 'polling'
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') {
        setSelectedItem(null);
        setBulkDecision(null);
        setBulkReason('');
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApprovals({ status: activeTab, page, pageSize: 50 });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [activeTab, page]);

  // Initial load + reload on tab/page change
  useEffect(() => { load(); }, [load]);

  // SSE for real-time updates; falls back to 30s polling on error
  const fallbackTimerRef = useRef(null);
  const esRef = useRef(null);

  const startFallbackPolling = useCallback(() => {
    if (fallbackTimerRef.current) return;
    fallbackTimerRef.current = setInterval(() => load(), 30000);
  }, [load]);

  const stopFallbackPolling = useCallback(() => {
    if (fallbackTimerRef.current) {
      clearInterval(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    const url = getApprovalStreamUrl();
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;
    setStreamStatus('connecting');

    es.addEventListener('connected', () => {
      setStreamStatus('live');
      stopFallbackPolling();
    });

    es.addEventListener('approval_update', () => {
      load();
      setLastUpdated(Date.now());
    });

    es.onerror = () => {
      setStreamStatus('polling');
      startFallbackPolling();
    };

    return () => {
      es.close();
      esRef.current = null;
      stopFallbackPolling();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const togglePause = useCallback(() => {
    if (esRef.current && esRef.current.readyState !== EventSource.CLOSED) {
      esRef.current.close();
      esRef.current = null;
      setStreamStatus('polling');
      startFallbackPolling();
    } else {
      // Reopen SSE
      stopFallbackPolling();
      const url = getApprovalStreamUrl();
      const es = new EventSource(url, { withCredentials: true });
      esRef.current = es;
      setStreamStatus('connecting');
      es.addEventListener('connected', () => setStreamStatus('live'));
      es.addEventListener('approval_update', () => { load(); setLastUpdated(Date.now()); });
      es.onerror = () => { setStreamStatus('polling'); startFallbackPolling(); };
    }
  }, [load, startFallbackPolling, stopFallbackPolling]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    localStorage.setItem('approvals_status_filter', tab);
    setPage(1);
    setSelectedItem(null);
  };

  const handleAction = async (item, mode, reason) => {
    setActionLoading(true);
    setActionError(null);
    try {
      if (mode === 'approve') {
        await approveRequest(item.id, reason);
      } else {
        await denyRequest(item.id, reason);
      }
      setSelectedItem(null);
      await load();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setActionLoading(false);
    }
  };

  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function selectAllPending(pendingItems) { setSelectedIds(new Set(pendingItems.map(i => i.id))); }
  function clearSelection() { setSelectedIds(new Set()); }

  async function executeBulkDecision() {
    setBulkBusy(true);
    const actionFn = bulkDecision === 'approve' ? approveRequest : denyRequest;
    const ids = [...selectedIds];
    try {
      await Promise.all(ids.map(id => actionFn(id, bulkReason)));
      clearSelection();
      setBulkDecision(null);
      setBulkReason('');
      await load();
    } catch (e) {
      alert(`Some actions failed: ${e.message}`);
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="space-y-4 min-w-0">
      <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">Approvals</h1>
      <SectionTabBar
        tabs={[
          { key: 'queue', label: 'Queue' },
          { key: 'exceptions', label: 'Exceptions' },
        ]}
        activeTab={sectionTab}
        onChange={setSectionTab}
      />

      {sectionTab === 'queue' && (
      <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
          <div>
            <div className="flex items-center gap-2">
              {/* Stream status badge */}
              <span
                title={streamStatus === 'live' ? 'Receiving real-time updates via SSE' : streamStatus === 'polling' ? 'SSE unavailable — polling every 30s' : 'Connecting to real-time stream...'}
                className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${
                  streamStatus === 'live'
                    ? 'bg-detec-teal-500/15 text-detec-teal-500 border-detec-teal-500/30'
                    : streamStatus === 'polling'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    : 'bg-detec-surface text-detec-ink-secondary border-detec-ui-border'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${
                  streamStatus === 'live' ? 'bg-detec-teal-500' : streamStatus === 'polling' ? 'bg-amber-400' : 'bg-detec-ink-secondary'
                }`} />
                {streamStatus === 'live' ? 'Live' : streamStatus === 'polling' ? 'Polling' : 'Connecting'}
              </span>
            </div>
            <p className="text-sm text-detec-ink-secondary mt-0.5">
              Review and action tool execution requests that require human approval.
            </p>
          </div>
          <button
            onClick={togglePause}
            className="text-xs text-detec-ink-secondary hover:text-detec-ink-primary border border-detec-ui-border/50 rounded px-2 py-1 transition-colors"
            title={streamStatus === 'polling' ? 'Reconnect SSE stream' : 'Pause live stream'}
          >
            {streamStatus === 'polling' ? 'Reconnect' : 'Pause'}
          </button>
        </div>
        {loading && <ApertureSpinner size="sm" label="Loading approvals" />}
      </div>

      {/* Enforcement posture callout */}
      <div className="rounded-detec-md border border-amber-500/30 bg-amber-500/5 px-4 py-3 flex items-start gap-3">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5" aria-hidden="true">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <div className="text-sm">
          <p className="text-detec-ink-primary font-medium">Enforcement behavior depends on posture</p>
          <p className="text-detec-ink-secondary mt-0.5">
            <strong className="text-detec-ink-primary">Active posture:</strong> detected processes are suspended (SIGSTOP) while awaiting a decision.{' '}
            <strong className="text-detec-ink-primary">Passive / audit posture:</strong> approval requests are logged and surfaced here, but execution is not blocked.
            Check your enforcement posture in Admin &gt; Server Settings.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="inline-flex rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-0.5">
        {TABS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleTabChange(value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              activeTab === value
                ? 'bg-detec-slate-200 text-detec-ink-primary'
                : 'text-detec-ink-secondary hover:text-detec-ink-primary hover:bg-detec-slate-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Errors */}
      <ApiErrorBanner error={error} onDismiss={() => setError(null)} />
      <ApiErrorBanner error={actionError} onDismiss={() => setActionError(null)} />

      {/* Empty state */}
      {items.length === 0 && !loading && !error && <EmptyState tab={activeTab} />}

      {/* Bulk action bar */}
      {activeTab === 'pending' && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 bg-detec-slate-50 border border-detec-ui-border rounded-detec-md mb-4">
          <span className="text-sm text-detec-ink-secondary">{selectedIds.size} selected</span>
          <button className="px-3 py-1 text-xs rounded bg-emerald-500 text-white hover:bg-emerald-600" onClick={() => setBulkDecision('approve')}>Approve all</button>
          <button className="px-3 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600" onClick={() => setBulkDecision('deny')}>Deny all</button>
          <button className="text-xs text-detec-ink-secondary hover:text-detec-ink-primary ml-auto" onClick={clearSelection}>Clear selection</button>
        </div>
      )}

      {/* Table */}
      {items.length > 0 && (
        <div className="rounded-detec-md border border-detec-ui-border/50 overflow-x-auto overflow-hidden">
          <table className="w-full text-left min-w-[700px]" aria-label="Approval requests">
            <thead>
              <tr className="bg-detec-surface/80 border-b border-detec-ui-border/50">
                {activeTab === 'pending' && (
                  <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider w-8">
                    <input
                      type="checkbox"
                      onChange={e => {
                        const sortedPending = [...items].sort((a, b) => new Date(a.requested_at) - new Date(b.requested_at));
                        e.target.checked ? selectAllPending(sortedPending) : clearSelection();
                      }}
                      checked={selectedIds.size === items.length && items.length > 0}
                    />
                  </th>
                )}
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider hidden md:table-cell">Endpoint</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Confidence</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider hidden lg:table-cell">Policy rule</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Requested at</th>
                {activeTab === 'pending' && (
                  <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Age</th>
                )}
                <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Status</th>
                {activeTab === 'pending' && (
                  <th className="px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {(activeTab === 'pending'
                ? [...items].sort((a, b) => new Date(a.requested_at) - new Date(b.requested_at))
                : items
              ).map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-detec-ui-border/40 hover:bg-detec-surface/40 cursor-pointer"
                  onClick={() => setSelectedItem(item)}
                >
                  {activeTab === 'pending' && (
                    <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selectedIds.has(item.id)} onChange={() => toggleSelect(item.id)} />
                    </td>
                  )}
                  <td className="px-4 py-3 text-sm font-mono text-detec-ink-primary">{item.tool_name}</td>
                  <td className="px-4 py-3 text-sm text-detec-ink-secondary hidden md:table-cell">
                    {item.endpoint_id ? item.endpoint_id.slice(0, 12) + '…' : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-ink-secondary">
                    <span className="font-mono">{fmtPct(item.confidence_score)}</span>
                    {item.confidence_band && (
                      <span className="ml-1.5 text-xs text-detec-ink-secondary opacity-70">({item.confidence_band})</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-detec-ink-secondary hidden lg:table-cell">
                    {item.policy_rule_id ? item.policy_rule_id.slice(0, 16) + '…' : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-ink-secondary whitespace-nowrap">
                    {fmtDate(item.requested_at)}
                  </td>
                  {activeTab === 'pending' && (
                    <td className="px-4 py-3 text-sm text-detec-ink-secondary whitespace-nowrap">
                      {formatAge(item.requested_at)}
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${statusBadgeClass(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>
                  </td>
                  {activeTab === 'pending' && (
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAction(item, 'approve', undefined)}
                          disabled={actionLoading}
                          className="px-2.5 py-1 text-xs font-medium rounded-md bg-green-600 hover:bg-green-700 text-white disabled:opacity-50 transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => { setSelectedItem(item); }}
                          disabled={actionLoading}
                          className="px-2.5 py-1 text-xs font-medium rounded-md bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors"
                          title="Open drawer to deny with reason"
                        >
                          Deny
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm text-detec-ink-secondary hover:text-detec-ink-primary disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-detec-ink-secondary">
            Page {page} of {Math.ceil(total / 50)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * 50 >= total}
            className="px-3 py-1.5 text-sm text-detec-ink-secondary hover:text-detec-ink-primary disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}

      {/* Detail drawer */}
      {selectedItem && (
        <DetailDrawer
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          onAction={handleAction}
          actionLoading={actionLoading}
          onNavigate={onNavigate}
        />
      )}

      {/* Bulk decision modal */}
      {bulkDecision && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-detec-surface border border-detec-ui-border rounded-detec-md p-6 w-96 space-y-4">
            <h2 className="font-semibold text-detec-ink-primary capitalize">{bulkDecision} {selectedIds.size} requests</h2>
            <div className="flex flex-wrap gap-1 mb-2">
              {(REASON_TEMPLATES[bulkDecision] || []).map(t => (
                <button key={t} className="text-xs px-2 py-0.5 rounded border border-detec-ui-border hover:bg-detec-slate-100" onClick={() => setBulkReason(t)}>{t}</button>
              ))}
            </div>
            <textarea className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ink-primary" rows={2} placeholder="Reason..." value={bulkReason} onChange={e => setBulkReason(e.target.value)} />
            <div className="flex gap-2">
              <button className="flex-1 py-1.5 text-sm rounded bg-detec-brand text-white hover:opacity-90 disabled:opacity-50" disabled={bulkBusy || !bulkReason.trim()} onClick={executeBulkDecision}>{bulkBusy ? 'Processing…' : 'Confirm'}</button>
              <button className="flex-1 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ink-secondary" onClick={() => { setBulkDecision(null); setBulkReason(''); }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
      </div>
      )}

      {sectionTab === 'exceptions' && (
        <ExceptionsPage embedded />
      )}
    </div>
  );
}
