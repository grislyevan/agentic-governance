import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchSessionReport } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import BehaviorChainTimeline from '../components/viz/BehaviorChainTimeline';
import ConfidenceEvidenceStack from '../components/viz/ConfidenceEvidenceStack';
import TriageActions from '../components/dashboard/TriageActions';
import Toast from '../components/ui/Toast';

/* ── Timeline type config ── */

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
};

const VERDICT_STYLES = {
  high_risk: 'bg-detec-enforce-blockBg text-detec-enforce-block border-detec-enforce-block/30',
  risky: 'bg-detec-enforce-approvalBg text-detec-enforce-approval border-detec-enforce-approval/30',
  interesting: 'bg-detec-enforce-warnBg text-detec-enforce-warn border-detec-enforce-warn/30',
  benign: 'bg-detec-edge-subtle text-detec-ink-secondary border-detec-edge',
};

/* ── Evidence panel for timeline entries ── */

function SessionEvidencePanel({ entry, sessionTopRiskSignals, onClose }) {
  if (!entry) return null;
  const signals = [entry.type];
  if (sessionTopRiskSignals?.length) {
    const typeToLabel = { shell_exec: 'shell execution', file_write: 'file write', llm: 'LLM call', network: 'network access', git: 'repo modification' };
    const related = sessionTopRiskSignals.filter(s => typeToLabel[entry.type] === s || s.includes(entry.type));
    related.forEach(s => { if (!signals.includes(s)) signals.push(s); });
  }
  return (
    <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-4 mt-2 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-data-xs font-data font-medium text-detec-ink-secondary uppercase tracking-wider">Evidence Detail</span>
        <button type="button" onClick={onClose} className="text-data-xs font-data text-detec-ink-secondary hover:text-detec-ink-primary">Close</button>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div><dt className="text-data-xs text-detec-ink-tertiary">Process</dt><dd className="text-data-sm font-data text-detec-ink-primary">{entry.process_name ?? '\u2014'}</dd></div>
        <div><dt className="text-data-xs text-detec-ink-tertiary">PID</dt><dd className="text-data-sm font-data text-detec-ink-primary tabular-nums">{entry.pid != null ? entry.pid : '\u2014'}</dd></div>
        <div><dt className="text-data-xs text-detec-ink-tertiary">Parent</dt><dd className="text-data-sm font-data text-detec-ink-primary">{entry.parent_process_name ?? '\u2014'}</dd></div>
        <div><dt className="text-data-xs text-detec-ink-tertiary">Parent PID</dt><dd className="text-data-sm font-data text-detec-ink-primary tabular-nums">{entry.parent_pid != null ? entry.parent_pid : '\u2014'}</dd></div>
      </dl>
      <div>
        <dt className="text-data-xs text-detec-ink-tertiary mb-1">Triggered signals</dt>
        <dd className="flex flex-wrap gap-1">
          {signals.map((s, i) => (
            <span key={i} className="text-data-xs font-data px-1.5 py-0.5 rounded-detec bg-detec-raised border border-detec-edge text-detec-ink-secondary">{s}</span>
          ))}
        </dd>
      </div>
    </div>
  );
}

/* ── Stat cell ── */

function StatCell({ label, value, mono = false }) {
  return (
    <div>
      <span className="text-data-xs font-data text-detec-ink-tertiary uppercase tracking-wider">{label}</span>
      <p className={`text-data-sm mt-0.5 text-detec-ink-primary ${mono ? 'font-data tabular-nums' : ''}`}>{value || '\u2014'}</p>
    </div>
  );
}

/* ── Main component ── */

export default function SessionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [copyLinkFeedback, setCopyLinkFeedback] = useState(false);
  const [toast, setToast] = useState(null);

  const copySessionLink = useCallback(() => {
    navigator.clipboard.writeText(`/sessions/${id}`).then(() => {
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

  useEffect(() => { load(); }, [load]);

  const exportMarkdown = () => {
    const lines = [
      '# Agent Session Report', '',
      `- **Tool:** ${report.tool}`,
      `- **Endpoint:** ${report.endpoint_id || '\u2014'}`,
      `- **Session risk:** ${report.session_risk != null ? (report.session_risk * 100).toFixed(0) + '%' : '\u2014'}`,
      `- **Confidence:** ${report.session_confidence != null ? (report.session_confidence * 100).toFixed(0) + '%' : '\u2014'}`,
      `- **Verdict:** ${report.session_verdict || '\u2014'}`, '',
      '## Timeline', '--------',
      ...(timeline.length ? timeline.map(e => `${e.at}  ${e.label}`) : ['(no timeline)']), '',
      '## Evidence', '--------',
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

  /* ── Loading / Error states ── */

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <ApertureSpinner size="lg" label="Loading session" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="space-y-4">
        <button type="button" onClick={() => navigate('/detections')} className="text-data-sm font-data text-detec-ink-secondary hover:text-detec-ink-primary">
          &larr; Back to Detections
        </button>
        <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-blockBg px-4 py-3 text-sm text-detec-enforce-block">
          {error || 'Session not found'}
        </div>
      </div>
    );
  }

  /* ── Data extraction ── */

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
  const verdictStyle = VERDICT_STYLES[report.session_verdict] || VERDICT_STYLES.benign;

  return (
    <div className="space-y-5 min-w-0">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => navigate('/detections')} className="text-data-sm font-data text-detec-ink-secondary hover:text-detec-ink-primary shrink-0">
            &larr; Detections
          </button>
          <h1 className="text-lg font-semibold text-detec-ink-primary truncate">
            {report.tool}
          </h1>
          {report.session_verdict && (
            <span className={`text-data-xs font-data font-medium px-2 py-0.5 rounded-detec border capitalize ${verdictStyle}`}>
              {report.session_verdict.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap shrink-0">
          <button type="button" onClick={copySessionLink} className="px-2.5 py-1 rounded-detec border border-detec-edge text-data-sm font-data text-detec-ink-secondary hover:text-detec-ink-primary hover:border-detec-edge-emphasis transition-colors">
            {copyLinkFeedback ? 'Copied!' : 'Copy link'}
          </button>
          <button type="button" onClick={exportMarkdown} className="px-2.5 py-1 rounded-detec border border-detec-edge text-data-sm font-data text-detec-ink-secondary hover:text-detec-ink-primary hover:border-detec-edge-emphasis transition-colors">
            Export MD
          </button>
          <button type="button" onClick={exportJson} className="px-2.5 py-1 rounded-detec border border-detec-edge text-data-sm font-data text-detec-ink-secondary hover:text-detec-ink-primary hover:border-detec-edge-emphasis transition-colors">
            Export JSON
          </button>
        </div>
      </div>

      <TriageActions report={report} onToast={setToast} />

      {/* ── Behavioral Chain (HERO — signature element) ── */}
      {(strongestSubchain.length > 0 || chains.length > 0) && (
        <section className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-3">
            {strongestSubchain.length > 0 ? 'Strongest Behavioral Chain' : 'Behavior Chains'}
          </h2>
          {strongestSubchain.length > 0 && (
            <BehaviorChainTimeline chains={[strongestSubchain.join(' -> ')]} />
          )}
          {chains.length > 0 && strongestSubchain.length > 0 && (
            <div className="mt-4 pt-3 border-t border-detec-edge-subtle">
              <h3 className="text-data-xs font-data text-detec-ink-tertiary mb-2">All chains ({chains.length})</h3>
              <BehaviorChainTimeline chains={chains} compact />
            </div>
          )}
          {chains.length > 0 && strongestSubchain.length === 0 && (
            <BehaviorChainTimeline chains={chains} />
          )}
        </section>
      )}

      {/* ── Two-column: Risk Summary + Confidence Evidence ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Risk summary — 2 cols */}
        <section className="lg:col-span-2 rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-3">Risk Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCell label="Duration" value={report.duration_seconds != null ? `${report.duration_seconds}s` : null} mono />
            <StatCell label="Actions" value={actionsCount} mono />
            <StatCell
              label="Session Risk"
              value={report.session_risk != null ? `R${report.session_risk >= 0.75 ? '4' : report.session_risk >= 0.5 ? '3' : report.session_risk >= 0.25 ? '2' : '1'} (${(report.session_risk * 100).toFixed(0)}%)` : null}
              mono
            />
            <StatCell label="Confidence" value={report.session_confidence != null ? `${(report.session_confidence * 100).toFixed(0)}%` : null} mono />
            <StatCell label="Verdict" value={report.session_verdict?.replace(/_/g, ' ')} />
            <StatCell label="Action" value={report.recommended_action} />
          </div>
        </section>

        {/* Confidence evidence stack — 1 col */}
        <section className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-3">Confidence Evidence</h2>
          <ConfidenceEvidenceStack
            composite={report.session_confidence}
            sources={report.attribution_sources}
          />
        </section>
      </div>

      {/* ── Timeline ── */}
      {timeline.length > 0 && (
        <section className="rounded-detec-md border border-detec-edge bg-detec-surface overflow-hidden">
          <div className="px-4 py-3 border-b border-detec-edge-subtle">
            <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider">
              Timeline ({timeline.length} events)
            </h2>
          </div>
          <ul className="divide-y divide-detec-edge-subtle">
            {timeline.map((entry, idx) => (
              <li
                key={idx}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedEntry(selectedEntry === entry ? null : entry)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedEntry(selectedEntry === entry ? null : entry); } }}
                className={`px-4 py-2 flex items-baseline gap-3 text-data-sm cursor-pointer hover:bg-detec-raised/50 transition-colors ${selectedEntry === entry ? 'bg-detec-raised/30' : ''}`}
                aria-expanded={selectedEntry === entry}
              >
                <span className="text-detec-ink-tertiary shrink-0 w-6 text-center" aria-hidden="true">
                  {TIMELINE_TYPE_ICONS[entry.type] ?? ''}
                </span>
                <span className="font-data text-detec-ink-tertiary shrink-0 tabular-nums w-16">{entry.at}</span>
                <span className="text-detec-ink-primary truncate">{entry.label}</span>
                <span className="text-data-xs font-data text-detec-ink-tertiary shrink-0 ml-auto">
                  {TIMELINE_TYPE_LABELS[entry.type] || entry.type || ''}
                </span>
              </li>
            ))}
          </ul>
          {selectedEntry && (
            <div className="px-4 pb-3">
              <SessionEvidencePanel
                entry={selectedEntry}
                sessionTopRiskSignals={report.top_risk_signals}
                onClose={() => setSelectedEntry(null)}
              />
            </div>
          )}
        </section>
      )}

      {/* ── Key Evidence ── */}
      {evidence.length > 0 && (
        <section className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-2">Key Evidence</h2>
          <ul className="space-y-1">
            {evidence.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-data-sm text-detec-ink-primary">
                <span className="text-detec-ink-tertiary shrink-0 mt-0.5">&bull;</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Policy Simulation ── */}
      {Object.keys(sim).length > 0 && (
        <section className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <h2 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-3">Policy Simulation</h2>
          <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Object.entries(sim).map(([preset, outcome]) => (
              <div key={preset}>
                <dt className="text-data-xs font-data text-detec-ink-tertiary capitalize">{preset}</dt>
                <dd className="text-data-sm font-data text-detec-ink-primary mt-0.5">{outcome}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {/* ── Empty state ── */}
      {timeline.length === 0 && strongestSubchain.length === 0 && chains.length === 0 && evidence.length === 0 && Object.keys(sim).length === 0 && (
        <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-8 text-center">
          <p className="text-data-sm font-data text-detec-ink-tertiary">No timeline or evidence for this session</p>
          <p className="text-data-xs font-data text-detec-ink-disabled mt-1">Aggregated from detection events only</p>
        </div>
      )}

      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
