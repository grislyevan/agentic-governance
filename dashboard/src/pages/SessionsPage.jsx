import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSessionReports } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';

const VERDICT_COLORS = {
  benign: 'bg-detec-teal-500/15 text-detec-teal-500',
  interesting: 'bg-detec-brand/10 text-detec-brand',
  risky: 'bg-amber-500/15 text-amber-400',
  high_risk: 'bg-detec-enforce-block/15 text-detec-enforce-block',
};

function VerdictBadge({ verdict }) {
  if (!verdict) return <span className="text-detec-ink-secondary text-xs">-</span>;
  const colors = VERDICT_COLORS[verdict] || 'bg-detec-slate-200 text-detec-ink-secondary';
  const label = verdict.replace(/_/g, ' ');
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium capitalize ${colors}`}>
      {label}
    </span>
  );
}

function ConfidenceCell({ value }) {
  if (value == null) return <span className="text-detec-ink-secondary text-xs">-</span>;
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? 'bg-detec-teal-500' :
    pct >= 50 ? 'bg-amber-400' :
    'bg-detec-ink-tertiary';
  return (
    <div className="flex items-center gap-2">
      <div className="w-10 h-1.5 bg-detec-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-detec-ink-secondary tabular-nums">{pct}%</span>
    </div>
  );
}

function ActionsSummary({ report }) {
  const ts = report.timeline_summary;
  if (ts && typeof ts === 'object' && Object.keys(ts).length > 0) {
    const parts = Object.entries(ts)
      .filter(([, n]) => n > 0)
      .map(([k, n]) => `${k}(${n})`)
      .slice(0, 5);
    return <span className="text-xs text-detec-ink-primary font-mono">{parts.join(', ') || '-'}</span>;
  }
  const a = report.actions;
  if (a && (a.shell_commands != null || a.file_writes != null || a.model_calls != null)) {
    const parts = [];
    if (a.shell_commands != null) parts.push(`shell(${a.shell_commands})`);
    if (a.file_writes != null) parts.push(`file_write(${a.file_writes})`);
    if (a.model_calls != null) parts.push(`llm(${a.model_calls})`);
    if (a.file_reads != null) parts.push(`file_read(${a.file_reads})`);
    return <span className="text-xs text-detec-ink-primary font-mono">{parts.join(', ') || '-'}</span>;
  }
  return <span className="text-detec-ink-secondary text-xs">-</span>;
}

export default function SessionsPage({ embedded } = {}) {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessionReports(undefined, { limit: 100 });
      setReports(data.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4 min-w-0">
      {!embedded && <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">
          Agent Sessions
        </h1>
        {loading && <ApertureSpinner size="sm" label="Loading sessions" />}
      </div>}
      {embedded && loading && <ApertureSpinner size="sm" label="Loading sessions" />}

      {error && (
        <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          <p>{error}</p>
          <p className="text-detec-ink-secondary mt-1 text-xs">Check the connection and try again.</p>
        </div>
      )}

      {!loading && !error && (
        <div className="rounded-detec-md border border-detec-ui-border/50 overflow-x-auto overflow-hidden">
          <table className="w-full text-left min-w-[640px]" aria-label="Agent sessions">
            <thead>
              <tr className="bg-detec-surface/80 border-b border-detec-ui-border/50">
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Time</th>
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Endpoint</th>
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Tool</th>
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Verdict</th>
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Confidence</th>
                <th scope="col" className="px-3 sm:px-4 py-3 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center">
                    <p className="text-detec-ink-secondary text-sm font-medium">No session reports yet</p>
                    <p className="text-detec-ink-secondary text-xs mt-1">Sessions appear when detection events are aggregated by endpoint and tool.</p>
                  </td>
                </tr>
              ) : (
                reports.map((report) => {
                  const sessionId = report.session_report_id ?? report.id;
                  return (
                  <tr
                    key={sessionId || `${report.endpoint_id}-${report.tool}-${report.started_at}`}
                    onClick={() => sessionId && navigate(`/sessions/${sessionId}`)}
                    className="border-b border-detec-ui-border/50 hover:bg-detec-slate-100 cursor-pointer transition-colors"
                  >
                    <td className="px-3 sm:px-4 py-3 text-sm text-detec-ink-primary whitespace-nowrap">
                      {report.started_at ? new Date(report.started_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-3 sm:px-4 py-3 text-sm text-detec-ink-primary font-mono truncate max-w-[120px]" title={report.endpoint_id}>
                      {report.endpoint_id || '-'}
                    </td>
                    <td className="px-3 sm:px-4 py-3 text-sm text-detec-ink-primary">{report.tool || '-'}</td>
                    <td className="px-3 sm:px-4 py-3">
                      <VerdictBadge verdict={report.session_verdict} />
                    </td>
                    <td className="px-3 sm:px-4 py-3">
                      <ConfidenceCell value={report.session_confidence} />
                    </td>
                    <td className="px-3 sm:px-4 py-3">
                      <ActionsSummary report={report} />
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
