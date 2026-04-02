import { useState, useEffect } from 'react';
import { fetchAuditLog, getApiConfig } from '../../lib/api';
import ApertureSpinner from '../branding/ApertureSpinner';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeSince(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '—';
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days} day${days !== 1 ? 's' : ''} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months !== 1 ? 's' : ''} ago`;
  const years = Math.floor(months / 12);
  return `${years} year${years !== 1 ? 's' : ''} ago`;
}

function actionBadgeClass(action) {
  if (!action) return 'bg-slate-100 text-slate-500 border-slate-200';
  if (action === 'policy.created') return 'bg-teal-100 text-teal-700 border-teal-200';
  if (action === 'policy.updated') return 'bg-amber-100 text-amber-700 border-amber-200';
  if (action === 'policy.deleted') return 'bg-red-100 text-red-700 border-red-200';
  if (action === 'policy.restore_defaults' || action === 'policy.preset_applied') {
    return 'bg-blue-100 text-blue-700 border-blue-200';
  }
  return 'bg-slate-100 text-slate-500 border-slate-200';
}

function actionLabel(action) {
  const labels = {
    'policy.created': 'Created',
    'policy.updated': 'Updated',
    'policy.deleted': 'Deleted',
    'policy.restore_defaults': 'Defaults Restored',
    'policy.preset_applied': 'Preset Applied',
  };
  return labels[action] || action;
}

function formatFieldValue(field, value) {
  if (value === null || value === undefined) return <span className="text-detec-ui-muted italic">null</span>;
  if (field === 'is_active') {
    return <span>{value ? 'Enabled' : 'Disabled'}</span>;
  }
  if (field === 'parameters') {
    return (
      <pre className="text-xs font-mono whitespace-pre-wrap break-all">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span>{String(value)}</span>;
}

const DIFF_FIELDS = ['is_active', 'parameters', 'description', 'rule_id', 'rule_version', 'category'];

function DiffTable({ before, after }) {
  const changed = DIFF_FIELDS.filter(
    (f) => (f in before || f in after) && JSON.stringify(before[f]) !== JSON.stringify(after[f])
  );
  if (changed.length === 0) return null;
  return (
    <table className="w-full text-xs border border-detec-ui-border rounded mt-2 overflow-hidden">
      <thead>
        <tr className="bg-detec-slate-50 border-b border-detec-ui-border">
          <th className="text-left px-2 py-1 font-semibold text-detec-ui-muted w-1/4">Field</th>
          <th className="text-left px-2 py-1 font-semibold text-detec-ui-muted w-[37.5%]">Before</th>
          <th className="text-left px-2 py-1 font-semibold text-detec-ui-muted w-[37.5%]">After</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-detec-ui-border">
        {changed.map((f) => (
          <tr key={f}>
            <td className="px-2 py-1 font-mono text-detec-ui-muted align-top">{f}</td>
            <td className="px-2 py-1 text-red-700 bg-red-50/50 align-top">
              {formatFieldValue(f, before[f])}
            </td>
            <td className="px-2 py-1 text-emerald-700 bg-emerald-50/50 align-top">
              {formatFieldValue(f, after[f])}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EntryDetail({ log }) {
  const action = log.action;
  const detail = log.detail || {};

  if (action === 'policy.created') {
    return (
      <p className="text-xs text-detec-ui-muted mt-1">
        Rule created
        {detail.rule_id && (
          <> — <span className="font-mono text-detec-ui-text">{detail.rule_id}</span></>
        )}
      </p>
    );
  }

  if (action === 'policy.deleted') {
    return <p className="text-xs text-detec-ui-muted mt-1">Rule deleted</p>;
  }

  if (action === 'policy.restore_defaults') {
    return <p className="text-xs text-detec-ui-muted mt-1">Defaults restored</p>;
  }

  if (action === 'policy.preset_applied') {
    return (
      <p className="text-xs text-detec-ui-muted mt-1">
        Preset applied
        {detail.preset_id && (
          <> — <span className="font-mono text-detec-ui-text">{detail.preset_id}</span></>
        )}
      </p>
    );
  }

  if (action === 'policy.updated') {
    if (detail.before && detail.after) {
      return <DiffTable before={detail.before} after={detail.after} />;
    }
    if (detail.fields_changed && Array.isArray(detail.fields_changed)) {
      return (
        <ul className="mt-1 space-y-0.5">
          {detail.fields_changed.map((f) => (
            <li key={f} className="text-xs text-detec-ui-muted font-mono">{f}</li>
          ))}
        </ul>
      );
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PolicyHistoryDrawer({ policy, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const config = getApiConfig();
    fetchAuditLog(config, { resourceType: 'policy', resourceId: policy.id, pageSize: 50 })
      .then((data) => {
        if (!cancelled) {
          setLogs(data.items || []);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message || 'Failed to load history');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [policy.id]);

  return (
    <div className="fixed inset-0 z-50 flex" aria-modal="true" role="dialog">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <div className="ml-auto w-full max-w-md flex flex-col bg-detec-ui-surface border-l border-detec-ui-border h-full overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-detec-ui-border shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono font-semibold text-detec-ui-text truncate">{policy.rule_id}</span>
            <span className="text-sm text-detec-ui-muted shrink-0">History</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-3 shrink-0 text-detec-ui-muted hover:text-detec-ui-text text-xl leading-none"
            aria-label="Close history drawer"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 px-5 py-4">
          {loading && (
            <div className="flex justify-center py-10">
              <ApertureSpinner size="sm" label="Loading history" />
            </div>
          )}

          {!loading && error && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && logs.length === 0 && (
            <p className="text-sm text-detec-ui-muted text-center py-10">
              No history found for this policy.
            </p>
          )}

          {!loading && !error && logs.length > 0 && (
            <ol className="space-y-4">
              {logs.map((log) => (
                <li key={log.id} className="flex gap-3">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center pt-0.5 shrink-0">
                    <div className="w-2 h-2 rounded-full bg-detec-ui-accent/60 ring-2 ring-detec-ui-accent/20" />
                    <div className="flex-1 w-px bg-detec-ui-border mt-1" />
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0 pb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded font-medium border ${actionBadgeClass(log.action)}`}
                      >
                        {actionLabel(log.action)}
                      </span>
                      <span className="text-xs text-detec-ui-muted">{timeSince(log.occurred_at)}</span>
                    </div>
                    {log.actor_id && (
                      <p className="mt-1 text-xs font-mono text-detec-ui-muted truncate max-w-[260px]">
                        {log.actor_id}
                      </p>
                    )}
                    <EntryDetail log={log} />
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
