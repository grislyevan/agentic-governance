import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchSessionReport } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import BehaviorChainViz from '../components/dashboard/BehaviorChainViz';

const TIMELINE_TYPE_LABELS = {
  llm: 'LLM call',
  shell_exec: 'Shell execution',
  exec: 'Process exec',
  file_write: 'File write',
  file_delete: 'File delete',
  file_modified: 'File modified',
  network: 'Network / outbound',
  git: 'Git operation',
  sequence_start: 'Sequence start',
  sequence_end: 'Sequence end',
};

const TIMELINE_TYPE_ICONS = {
  llm: '\u{1F916}',
  shell_exec: '\u{1F5A5}',
  exec: '\u{1F5A5}',
  file_write: '\u{1F4C4}',
  file_delete: '\u{1F4C4}',
  file_modified: '\u{1F4C4}',
  network: '\u{1F310}',
  git: '\u{1F331}',
  sequence_start: '',
  sequence_end: '',
};

function timelineTypeLabel(type) {
  return TIMELINE_TYPE_LABELS[type] || type || '-';
}

function timelineTypeIcon(type) {
  return TIMELINE_TYPE_ICONS[type] ?? '';
}

function SessionEvidencePanel({ entry, sessionTopRiskSignals, onClose }) {
  if (!entry) return null;
  const signals = [entry.type];
  if (sessionTopRiskSignals && sessionTopRiskSignals.length) {
    const typeToLabel = { shell_exec: 'shell execution', file_write: 'file write', llm: 'LLM call', network: 'network access', git: 'repo modification' };
    const related = sessionTopRiskSignals.filter(s => typeToLabel[entry.type] === s || s.includes(entry.type));
    related.forEach(s => { if (!signals.includes(s)) signals.push(s); });
  }
  return (
    <div className="rounded-lg border border-detec-ui-border bg-detec-ui-surface/80 p-4 mt-2 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-detec-ui-muted uppercase tracking-wider">Evidence</span>
        <button type="button" onClick={onClose} className="text-detec-ui-muted hover:text-detec-ui-text text-sm">Close</button>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
        <div><dt className="text-detec-ui-muted">Process</dt><dd className="text-detec-ui-text font-mono">{entry.process_name ?? '—'}</dd></div>
        <div><dt className="text-detec-ui-muted">PID</dt><dd className="text-detec-ui-text font-mono">{entry.pid != null ? entry.pid : '—'}</dd></div>
        <div><dt className="text-detec-ui-muted">Parent process</dt><dd className="text-detec-ui-text font-mono">{entry.parent_process_name ?? '—'}</dd></div>
        <div><dt className="text-detec-ui-muted">Parent PID</dt><dd className="text-detec-ui-text font-mono">{entry.parent_pid != null ? entry.parent_pid : '—'}</dd></div>
      </dl>
      <div>
        <dt className="text-detec-ui-muted text-xs mb-1">Triggered signals</dt>
        <dd className="text-detec-ui-text text-xs">
          {signals.map((s, i) => (
            <span key={i} className="inline-block mr-2 px-1.5 py-0.5 rounded bg-detec-slate-200">{s}</span>
          ))}
        </dd>
      </div>
    </div>
  );
}

export default function SessionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [copyLinkFeedback, setCopyLinkFeedback] = useState(false);

  const copySessionLink = useCallback(() => {
    const path = `/sessions/${id}`;
    navigator.clipboard.writeText(path).then(() => {
      setCopyLinkFeedback(true);
      setTimeout(() => setCopyLinkFeedback(false), 2000);
    });
  }, [id]);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessionReport(undefined, id);
      setReport(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ApertureSpinner size="lg" label="Loading session" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => navigate('/sessions')}
          className="text-sm text-detec-ui-muted hover:text-detec-ui-text"
        >
          Back to Sessions
        </button>
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          <p>{error || 'Session not found'}</p>
        </div>
      </div>
    );
  }

  const timeline = report.session_timeline || [];
  const chains = report.top_behavior_chains || [];
  const strongestSubchain = report.strongest_subchain || [];
  const evidence = report.key_evidence || [];
  const sim = report.policy_simulation || {};
  const actionsCount = timeline.length > 0
    ? timeline.length
    : (report.timeline_summary && typeof report.timeline_summary === 'object'
      ? Object.values(report.timeline_summary).reduce((a, b) => a + b, 0)
      : null);

  const exportMarkdown = () => {
    const lines = [
      '# Agent Session Report',
      '',
      `- **Tool:** ${report.tool}`,
      `- **Endpoint:** ${report.endpoint_id || '—'}`,
      `- **Session risk:** ${report.session_risk != null ? (report.session_risk * 100).toFixed(0) + '%' : '—'}`,
      `- **Confidence:** ${report.session_confidence != null ? (report.session_confidence * 100).toFixed(0) + '%' : '—'}`,
      `- **Verdict:** ${report.session_verdict || '—'}`,
      '',
      '## Timeline',
      '--------',
      ...(timeline.length ? timeline.map(e => `${e.at}  ${e.label}`) : ['(no timeline)']),
      '',
      '## Evidence',
      '--------',
      ...(evidence.length ? evidence.map(e => `- ${e}`) : ['(no evidence)']),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-report-${(report.tool || 'session').replace(/\s+/g, '-')}-${report.id || 'export'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-report-${(report.tool || 'session').replace(/\s+/g, '-')}-${report.id || 'export'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/sessions')}
            className="text-sm text-detec-ui-muted hover:text-detec-ui-text"
          >
            Back to Sessions
          </button>
          <h1 className="text-xl sm:text-2xl font-bold text-detec-ui-text">
            Session: {report.tool}
          </h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={copySessionLink}
            className="px-3 py-1.5 rounded-lg border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-ui-surface"
          >
            {copyLinkFeedback ? 'Copied!' : 'Copy session link'}
          </button>
          <button
            type="button"
            onClick={exportMarkdown}
            className="px-3 py-1.5 rounded-lg border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-ui-surface"
          >
            Export Markdown
          </button>
          <button
            type="button"
            onClick={exportJson}
            className="px-3 py-1.5 rounded-lg border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-ui-surface"
          >
            Export JSON
          </button>
        </div>
      </div>

      <section aria-labelledby="risk-summary-heading">
        <h2 id="risk-summary-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Risk summary</h2>
        <div className="rounded-lg border border-detec-ui-border/50 bg-detec-ui-surface/40 p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Duration</span>
            <p className="text-sm text-detec-ui-text mt-0.5">
              {report.duration_seconds != null ? `${report.duration_seconds}s` : '-'}
            </p>
          </div>
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Actions</span>
            <p className="text-sm text-detec-ui-text mt-0.5">{actionsCount ?? '-'}</p>
          </div>
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Session risk</span>
            <p className="text-sm text-detec-ui-text mt-0.5">
              {report.session_risk != null ? `R${report.session_risk >= 0.75 ? '4' : report.session_risk >= 0.5 ? '3' : report.session_risk >= 0.25 ? '2' : '1'} (${(report.session_risk * 100).toFixed(0)}%)` : '-'}
            </p>
          </div>
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Confidence</span>
            <p className="text-sm text-detec-ui-text mt-0.5">
              {report.session_confidence != null ? `${(report.session_confidence * 100).toFixed(0)}%` : '-'}
            </p>
          </div>
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Verdict</span>
            <p className="text-sm text-detec-ui-text mt-0.5 capitalize">{report.session_verdict?.replace(/_/g, ' ') || '-'}</p>
          </div>
          <div>
            <span className="text-xs text-detec-ui-muted uppercase tracking-wider">Recommended action</span>
            <p className="text-sm text-detec-ui-text mt-0.5">{report.recommended_action || '-'}</p>
          </div>
        </div>
      </section>

      {timeline.length > 0 && (
        <section aria-labelledby="timeline-heading">
          <h2 id="timeline-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Timeline</h2>
          <div className="rounded-lg border border-detec-ui-border/50 overflow-hidden">
            <ul className="divide-y divide-detec-slate-700/50">
              {timeline.map((entry, idx) => (
                <li
                  key={idx}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedEntry(selectedEntry === entry ? null : entry)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedEntry(selectedEntry === entry ? null : entry); } }}
                  className={`px-4 py-2 flex items-baseline gap-3 font-mono text-sm cursor-pointer hover:bg-detec-slate-100 ${selectedEntry === entry ? 'bg-detec-ui-surface/80' : ''}`}
                  aria-expanded={selectedEntry === entry}
                >
                  <span className="text-detec-ui-muted shrink-0 w-8" aria-hidden="true">{timelineTypeIcon(entry.type)}</span>
                  <span className="text-detec-ui-muted shrink-0">{entry.at}</span>
                  <span className="text-detec-ui-text">{entry.label}</span>
                  <span className="text-xs text-detec-ui-muted">{timelineTypeLabel(entry.type)}</span>
                </li>
              ))}
            </ul>
          </div>
          {selectedEntry && (
            <SessionEvidencePanel
              entry={selectedEntry}
              sessionTopRiskSignals={report.top_risk_signals}
              onClose={() => setSelectedEntry(null)}
            />
          )}
        </section>
      )}

      {strongestSubchain.length > 0 && (
        <section aria-labelledby="strongest-subchain-heading">
          <h2 id="strongest-subchain-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Strongest subchain</h2>
          <BehaviorChainViz chains={[strongestSubchain.join(' -> ')]} />
        </section>
      )}

      {chains.length > 0 && (
        <section aria-labelledby="chains-heading">
          <h2 id="chains-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Behavior chains</h2>
          <BehaviorChainViz chains={chains} />
        </section>
      )}

      {evidence.length > 0 && (
        <section aria-labelledby="evidence-heading">
          <h2 id="evidence-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Evidence</h2>
          <ul className="list-disc list-inside text-sm text-detec-ui-text space-y-1">
            {evidence.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {Object.keys(sim).length > 0 && (
        <section aria-labelledby="policy-sim-heading">
          <h2 id="policy-sim-heading" className="text-sm font-semibold text-detec-ui-text mb-3">Policy simulation</h2>
          <div className="rounded-lg border border-detec-ui-border/50 bg-detec-ui-surface/40 p-4">
            <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {Object.entries(sim).map(([preset, outcome]) => (
                <div key={preset}>
                  <dt className="text-xs text-detec-ui-muted capitalize">{preset}</dt>
                  <dd className="text-sm text-detec-ui-text mt-0.5">{outcome}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      )}

      {timeline.length === 0 && strongestSubchain.length === 0 && chains.length === 0 && evidence.length === 0 && Object.keys(sim).length === 0 && (
        <p className="text-sm text-detec-ui-muted">No timeline or evidence for this session (aggregated from detection events only).</p>
      )}
    </div>
  );
}
