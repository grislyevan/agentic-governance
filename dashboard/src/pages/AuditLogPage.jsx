import { useState, useEffect, useCallback } from 'react';
import { fetchAuditLog, generateComplianceReport } from '../lib/api';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';

const ACTION_FILTERS = [
  { value: '', label: 'All' },
  { value: 'enforcement.', label: 'Enforcement' },
  { value: 'enforcement.posture', label: 'Posture' },
  { value: 'enforcement.allow_list', label: 'Allow-list' },
];

function getActionBadgeClass(action) {
  if (!action || typeof action !== 'string') return 'bg-detec-slate-700/50 text-detec-slate-300 border-detec-slate-600/50';
  if (['enforcement.applied', 'enforcement.escalated', 'enforcement.failed'].includes(action)) {
    return 'bg-red-500/10 text-red-400 border-red-500/30';
  }
  if (action === 'enforcement.simulated') return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  if (['enforcement.allow_listed', 'enforcement.rate_limited'].includes(action)) {
    return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
  }
  if (['enforcement.posture_changed', 'enforcement.tenant_posture_changed'].includes(action)) {
    return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
  }
  if (['enforcement.allow_list_added', 'enforcement.allow_list_removed'].includes(action)) {
    return 'bg-teal-500/10 text-teal-400 border-teal-500/30';
  }
  return 'bg-detec-slate-700/50 text-detec-slate-300 border-detec-slate-600/50';
}

function formatActionLabel(action) {
  if (!action || typeof action !== 'string') return action || '';
  const labels = {
    'enforcement.applied': 'Enforcement Applied',
    'enforcement.escalated': 'Enforcement Escalated',
    'enforcement.failed': 'Enforcement Failed',
    'enforcement.simulated': 'Simulated',
    'enforcement.allow_listed': 'Allow-listed',
    'enforcement.rate_limited': 'Rate Limited',
    'enforcement.posture_changed': 'Posture Changed',
    'enforcement.tenant_posture_changed': 'Tenant Posture Changed',
    'enforcement.allow_list_added': 'Allow-list Added',
    'enforcement.allow_list_removed': 'Allow-list Removed',
  };
  return labels[action] || action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function renderDetail(detail) {
  if (!detail || typeof detail !== 'object') return String(detail || '');
  if ('new_posture' in detail) {
    const hostname = detail.hostname ? ` (${detail.hostname})` : '';
    const endpoints = detail.endpoints_updated != null ? ` · ${detail.endpoints_updated} endpoint(s)` : '';
    const transition = detail.old_posture != null ? `${detail.old_posture} → ` : '';
    return (
      <span className="text-detec-slate-300">
        {transition}{detail.new_posture}{hostname}{endpoints}
      </span>
    );
  }
  const enf = detail.enforcement;
  if (enf && typeof enf === 'object' && 'tactic' in enf) {
    const parts = [enf.tactic];
    if (enf.pids_killed != null) parts.push(`${enf.pids_killed} PID(s)`);
    if (enf.process_name) parts.push(enf.process_name);
    return (
      <span className="text-detec-slate-300">
        {parts.join(' · ')}
      </span>
    );
  }
  if ('pattern' in detail) {
    const type = detail.pattern_type ? ` (${detail.pattern_type})` : '';
    return (
      <span className="text-detec-slate-300 font-mono text-xs">
        {detail.pattern}{type}
      </span>
    );
  }
  return JSON.stringify(detail);
}

function toDateStr(d) {
  return d.toISOString().slice(0, 10);
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportStart, setExportStart] = useState(() => toDateStr(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)));
  const [exportEnd, setExportEnd] = useState(() => toDateStr(new Date()));
  const [exportFormat, setExportFormat] = useState('pdf');
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState(null);
  const [jsonPreview, setJsonPreview] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, pageSize: 50 };
      if (actionFilter) params.action = actionFilter;
      const data = await fetchAuditLog(undefined, params);
      setLogs(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter]);

  useEffect(() => { load(); }, [load]);

  const { lastUpdated, paused, togglePause } = usePolling(load);

  const handleExport = async () => {
    setExportLoading(true);
    setExportError(null);
    setJsonPreview(null);
    try {
      const result = await generateComplianceReport(exportStart, exportEnd, exportFormat);
      if (exportFormat === 'json') {
        setJsonPreview(result);
      } else {
        setExportModalOpen(false);
      }
    } catch (e) {
      setExportError(e.message);
    } finally {
      setExportLoading(false);
    }
  };

  const closeExportModal = () => {
    setExportModalOpen(false);
    setExportError(null);
    setJsonPreview(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-detec-slate-100">Audit Log</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExportModalOpen(true)}
            className="px-3 py-1.5 text-sm font-medium rounded-lg border border-detec-slate-600/50 bg-detec-slate-800/50 text-detec-slate-200 hover:bg-detec-slate-700/50 hover:border-detec-slate-500/50 transition-colors"
          >
            Export Compliance Report
          </button>
          {loading && <ApertureSpinner size="sm" label="Loading audit log" />}
        </div>
      </div>

      {exportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={closeExportModal}>
          <div
            className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-900/95 p-6 max-w-md w-full mx-4 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">Export Compliance Report</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-detec-slate-500 uppercase tracking-wider mb-1">Start date</label>
                <input
                  type="date"
                  value={exportStart}
                  onChange={(e) => setExportStart(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-detec-slate-600/50 bg-detec-slate-800 text-detec-slate-200 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-detec-slate-500 uppercase tracking-wider mb-1">End date</label>
                <input
                  type="date"
                  value={exportEnd}
                  onChange={(e) => setExportEnd(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-detec-slate-600/50 bg-detec-slate-800 text-detec-slate-200 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-detec-slate-500 uppercase tracking-wider mb-1">Format</label>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-detec-slate-600/50 bg-detec-slate-800 text-detec-slate-200 text-sm"
                >
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="pdf">PDF</option>
                </select>
              </div>
            </div>
            {exportError && (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                {exportError}
              </div>
            )}
            {jsonPreview && (
              <div className="mt-4 max-h-64 overflow-auto rounded-lg border border-detec-slate-700/50 bg-detec-slate-800/50 p-3">
                <pre className="text-xs text-detec-slate-300 whitespace-pre-wrap font-mono">
                  {JSON.stringify(jsonPreview, null, 2)}
                </pre>
                <button
                  onClick={() => window.open('data:application/json,' + encodeURIComponent(JSON.stringify(jsonPreview, null, 2)), '_blank')}
                  className="mt-2 text-xs text-detec-slate-400 hover:text-detec-slate-200"
                >
                  Open in new tab
                </button>
              </div>
            )}
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={closeExportModal}
                className="px-3 py-1.5 text-sm text-detec-slate-400 hover:text-detec-slate-200"
              >
                {jsonPreview ? 'Close' : 'Cancel'}
              </button>
              {!jsonPreview && (
                <button
                  onClick={handleExport}
                  disabled={exportLoading}
                  className="px-4 py-1.5 text-sm font-medium rounded-lg bg-detec-slate-700 text-detec-slate-200 hover:bg-detec-slate-600 disabled:opacity-50"
                >
                  {exportLoading ? 'Generating...' : 'Generate Report'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Filter</span>
        <div className="inline-flex rounded-lg border border-detec-slate-700/50 bg-detec-slate-800/50 p-0.5">
          {ACTION_FILTERS.map(({ value, label }) => (
            <button
              key={value || 'all'}
              onClick={() => { setActionFilter(value); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                actionFilter === value
                  ? 'bg-detec-slate-700 text-detec-slate-200'
                  : 'text-detec-slate-400 hover:text-detec-slate-200 hover:bg-detec-slate-700/50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      {logs.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
          <div className="mb-3 opacity-40">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <div className="text-detec-slate-400 text-sm font-medium mb-1">Audit log is empty</div>
          <div className="text-detec-slate-600 text-sm max-w-sm mx-auto">
            Every governance action gets a record. Once policies fire and enforcement decisions land,
            the trail starts here.
          </div>
        </div>
      )}

      {logs.length > 0 && (
        <div className="rounded-xl border border-detec-slate-700/50 overflow-x-auto overflow-hidden">
          <table className="w-full text-left min-w-[640px]" aria-label="Audit log entries">
            <thead>
              <tr className="bg-detec-slate-800/80 border-b border-detec-slate-700/50">
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Time</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Action</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider hidden md:table-cell">Actor</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider hidden lg:table-cell">Resource</th>
                <th className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-detec-slate-700/40 hover:bg-detec-slate-800/40">
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-slate-400 whitespace-nowrap">
                    {new Date(log.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-3 sm:px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${getActionBadgeClass(log.action)}`}>
                      {formatActionLabel(log.action)}
                    </span>
                  </td>
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-slate-400 hidden md:table-cell">
                    {log.actor_type === 'agent' ? (
                      <span className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 bg-detec-slate-700/50 border border-detec-slate-600/40">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-detec-slate-500 shrink-0" aria-hidden="true">
                          <circle cx="12" cy="12" r="3" />
                          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                        </svg>
                        <span className="text-xs text-detec-slate-400">Agent</span>
                        {log.actor_id ? <span className="text-detec-slate-600 ml-1 font-mono">{log.actor_id.slice(0, 8)}</span> : null}
                      </span>
                    ) : (
                      <>
                        <span className="font-mono text-xs">{log.actor_type}</span>
                        {log.actor_id ? <span className="text-detec-slate-600 ml-1">{log.actor_id.slice(0, 8)}</span> : null}
                      </>
                    )}
                  </td>
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-slate-400 hidden lg:table-cell">
                    {log.resource_type ? <span className="font-mono text-xs">{log.resource_type}</span> : null}
                    {log.resource_id ? <span className="text-detec-slate-600 ml-1">{log.resource_id.slice(0, 8)}</span> : null}
                  </td>
                  <td className="px-3 sm:px-4 py-3 text-sm text-detec-slate-500 max-w-xs">
                    {renderDetail(log.detail)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > 50 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm text-detec-slate-400 hover:text-detec-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-detec-slate-500">Page {page} of {Math.ceil(total / 50)}</span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page * 50 >= total}
            className="px-3 py-1.5 text-sm text-detec-slate-400 hover:text-detec-slate-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
