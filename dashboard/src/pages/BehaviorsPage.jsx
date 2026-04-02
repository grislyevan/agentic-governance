/**
 * BehaviorsPage — Behavioral detection visualization.
 *
 * Dedicated page for behavioral chain analysis:
 * - Recent behavioral chains (BEH-001 through BEH-004)
 * - Chain type breakdown
 * - Temporal heatmap (detections by hour)
 * - Drill-through to session detail
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSessionReports } from '../lib/api';
import BehaviorChainTimeline from '../components/viz/BehaviorChainTimeline';
import ConfidenceEvidenceStack from '../components/viz/ConfidenceEvidenceStack';
import ApertureSpinner from '../components/branding/ApertureSpinner';

/* ── Detection rule catalog ── */

const BEH_RULES = {
  'BEH-001': { name: 'Shell Fan-Out',         desc: '≥3 distinct shells in 60s at >0.20/s', icon: 'S', color: 'text-[#fb923c]' },
  'BEH-002': { name: 'Read-Modify-Write Loop', desc: 'Same file R→W cycle ≥3× in 120s',     icon: 'R', color: 'text-[#fbbf24]' },
  'BEH-003': { name: 'Sensitive → Outbound',   desc: 'Cred access then network in 300s',     icon: '!', color: 'text-[#f87171]' },
  'BEH-004': { name: 'Execution Chain',         desc: 'LLM → Shell → File/Git in ≤180s',     icon: 'E', color: 'text-[#60a5fa]' },
};

/* ── Chain type extraction from session data ── */

function extractBehaviorData(sessions) {
  const chains = [];
  const byRule = { 'BEH-001': 0, 'BEH-002': 0, 'BEH-003': 0, 'BEH-004': 0 };
  const byHour = Array(24).fill(0);

  for (const session of sessions) {
    const sessionChains = session.top_behavior_chains || [];
    const startedAt = session.started_at ? new Date(session.started_at) : null;
    const hour = startedAt ? startedAt.getHours() : null;

    for (const chain of sessionChains) {
      const steps = typeof chain === 'string' ? chain.split(/\s*->\s*/) : [];
      chains.push({
        chain,
        sessionId: session.session_report_id || session.id,
        tool: session.tool,
        verdict: session.session_verdict,
        confidence: session.session_confidence,
        startedAt,
      });

      // Classify chain to detection rule
      if (steps.some(s => s === 'shell_exec') && steps.length >= 3) byRule['BEH-001']++;
      if (steps.filter(s => s === 'file_write' || s === 'file_modified').length >= 2) byRule['BEH-002']++;
      if (steps.some(s => s === 'sensitive' || s === 'network')) byRule['BEH-003']++;
      if (steps.includes('llm') && steps.includes('shell_exec') && (steps.includes('file_write') || steps.includes('git'))) byRule['BEH-004']++;

      if (hour != null) byHour[hour]++;
    }
  }

  return { chains, byRule, byHour };
}

/* ── Temporal heatmap row ── */

function HourHeatmap({ byHour }) {
  const max = Math.max(...byHour, 1);

  return (
    <div className="space-y-2">
      <h3 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider">
        Detection Activity by Hour
      </h3>
      <div className="flex items-end gap-px h-16">
        {byHour.map((count, hour) => {
          const pct = Math.max((count / max) * 100, 4);
          const intensity = count === 0 ? 'bg-detec-edge-subtle' : count / max > 0.7 ? 'bg-detec-enforce-block' : count / max > 0.3 ? 'bg-detec-enforce-warn' : 'bg-detec-enforce-detect';
          return (
            <div key={hour} className="flex-1 flex flex-col items-center gap-0.5" title={`${hour}:00 — ${count} detection${count !== 1 ? 's' : ''}`}>
              <div className={`w-full rounded-t-sm ${intensity} transition-all`} style={{ height: `${pct}%` }} />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-data-xs font-data text-detec-ink-tertiary">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:00</span>
      </div>
    </div>
  );
}

/* ── Rule breakdown card ── */

function RuleBreakdown({ byRule }) {
  const total = Object.values(byRule).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-2">
      <h3 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider">
        Detection Rules
      </h3>
      <div className="space-y-1.5">
        {Object.entries(BEH_RULES).map(([ruleId, rule]) => {
          const count = byRule[ruleId] || 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <div key={ruleId} className="flex items-center gap-2">
              <span className={`w-5 h-5 rounded-detec flex items-center justify-center text-data-xs font-bold ${rule.color} bg-black/20 shrink-0`}>
                {rule.icon}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-data-sm font-data text-detec-ink-primary truncate">{rule.name}</span>
                  <span className="text-data-sm font-data text-detec-ink-secondary tabular-nums shrink-0">{count}</span>
                </div>
                <div className="h-1 rounded-full bg-detec-edge-subtle mt-0.5">
                  {pct > 0 && (
                    <div className="h-full rounded-full bg-detec-brand transition-all" style={{ width: `${pct}%` }} />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-data-xs font-data text-detec-ink-tertiary mt-1">{total} total chain{total !== 1 ? 's' : ''} detected</p>
    </div>
  );
}

/* ── Chain list row ── */

function ChainRow({ entry, onNavigate }) {
  const verdictColors = {
    high_risk: 'text-detec-enforce-block',
    risky: 'text-detec-enforce-approval',
    interesting: 'text-detec-enforce-warn',
    benign: 'text-detec-ink-tertiary',
  };

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-detec-md border border-detec-edge-subtle hover:border-detec-edge transition-colors group">
      {/* Chain visualization */}
      <div className="flex-1 min-w-0 overflow-x-auto">
        <BehaviorChainTimeline chains={[entry.chain]} compact />
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="text-data-xs font-data text-detec-ink-secondary">{entry.tool}</span>
        {entry.confidence != null && (
          <ConfidenceEvidenceStack composite={entry.confidence} compact />
        )}
        {entry.verdict && (
          <span className={`text-data-xs font-data font-medium capitalize ${verdictColors[entry.verdict] || 'text-detec-ink-secondary'}`}>
            {entry.verdict.replace(/_/g, ' ')}
          </span>
        )}
        {entry.startedAt && (
          <span className="text-data-xs font-data text-detec-ink-tertiary tabular-nums">
            {entry.startedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
        <button
          type="button"
          onClick={() => onNavigate(entry.sessionId)}
          className="text-data-xs font-data text-detec-brand hover:text-detec-brand-hover opacity-0 group-hover:opacity-100 transition-opacity"
        >
          Investigate →
        </button>
      </div>
    </div>
  );
}

/* ── Main page ── */

export default function BehaviorsPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessionReports(undefined, { limit: 100 });
      const items = data?.items || (Array.isArray(data) ? data : []);
      setSessions(items);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const { chains, byRule, byHour } = useMemo(() => extractBehaviorData(sessions), [sessions]);

  const handleNavigate = useCallback((sessionId) => {
    if (sessionId) navigate(`/sessions/${sessionId}`);
  }, [navigate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <ApertureSpinner size="lg" label="Analyzing behavior chains" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-blockBg px-4 py-3 text-sm text-detec-enforce-block">
        {error}
        <button type="button" onClick={load} className="ml-3 underline hover:no-underline">Retry</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold text-detec-ink-primary">Behavioral Analysis</h1>
        <p className="text-data-sm font-data text-detec-ink-secondary mt-0.5">
          Temporal pattern correlation across {sessions.length} session{sessions.length !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Rule breakdown */}
        <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <RuleBreakdown byRule={byRule} />
        </div>

        {/* Hour heatmap */}
        <div className="lg:col-span-2 rounded-detec-md border border-detec-edge bg-detec-surface p-4">
          <HourHeatmap byHour={byHour} />
        </div>
      </div>

      {/* Detection rule reference */}
      <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
        <h3 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-3">
          Detection Rule Reference
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {Object.entries(BEH_RULES).map(([ruleId, rule]) => (
            <div key={ruleId} className="flex items-start gap-2 py-1.5">
              <span className={`text-data-xs font-data font-bold ${rule.color} shrink-0 w-16`}>{ruleId}</span>
              <div className="min-w-0">
                <span className="text-data-sm font-data text-detec-ink-primary">{rule.name}</span>
                <p className="text-data-xs font-data text-detec-ink-tertiary">{rule.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chain list */}
      <div>
        <h3 className="text-data-sm font-data font-medium text-detec-ink-secondary uppercase tracking-wider mb-2">
          Recent Chains ({chains.length})
        </h3>
        {chains.length === 0 ? (
          <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-8 text-center">
            <p className="text-data-sm font-data text-detec-ink-tertiary">No behavioral chains detected in recent sessions</p>
            <p className="text-data-xs font-data text-detec-ink-disabled mt-1">Chains appear when AI tools execute multi-step sequences (LLM → Shell → File → Git)</p>
          </div>
        ) : (
          <div className="space-y-1">
            {chains.slice(0, 50).map((entry, idx) => (
              <ChainRow key={idx} entry={entry} onNavigate={handleNavigate} />
            ))}
            {chains.length > 50 && (
              <p className="text-data-xs font-data text-detec-ink-tertiary text-center py-2">
                Showing 50 of {chains.length} chains
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
