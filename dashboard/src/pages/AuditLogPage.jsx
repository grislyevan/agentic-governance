import { useState, useEffect, useCallback } from 'react';
import { fetchAuditLog } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';

export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLog(undefined, { page, pageSize: 50 });
      setLogs(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-detec-slate-100">Audit Log</h1>
        {loading && <ApertureSpinner size="sm" label="Loading audit log" />}
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
        <div className="rounded-xl border border-detec-slate-700/50 overflow-hidden">
          <table className="w-full text-left" aria-label="Audit log entries">
            <thead>
              <tr className="bg-detec-slate-800/80 border-b border-detec-slate-700/50">
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Time</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Action</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Actor</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Resource</th>
                <th className="px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-detec-slate-700/40 hover:bg-detec-slate-800/40">
                  <td className="px-4 py-3 text-sm text-detec-slate-400 whitespace-nowrap">
                    {new Date(log.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-slate-200 font-medium">{log.action}</td>
                  <td className="px-4 py-3 text-sm text-detec-slate-400">
                    <span className="font-mono text-xs">{log.actor_type}</span>
                    {log.actor_id && <span className="text-detec-slate-600 ml-1">{log.actor_id.slice(0, 8)}</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-slate-400">
                    {log.resource_type && <span className="font-mono text-xs">{log.resource_type}</span>}
                    {log.resource_id && <span className="text-detec-slate-600 ml-1">{log.resource_id.slice(0, 8)}</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-detec-slate-500 max-w-xs truncate">
                    {typeof log.detail === 'object' ? JSON.stringify(log.detail) : String(log.detail || '')}
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
