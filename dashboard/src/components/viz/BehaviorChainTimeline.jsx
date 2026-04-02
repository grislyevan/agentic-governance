/**
 * BehaviorChainTimeline — Horizontal connected causal nodes.
 *
 * Renders a behavioral detection chain as connected temporal nodes:
 *   [Network: api.anthropic.com] ──12ms──▶ [Shell: git diff] ──340ms──▶ [File: modified] ──▶ [Git: commit]
 *
 * Props:
 *   chains  - array of chain strings ("llm -> shell_exec -> file_write -> git")
 *             OR array of chain objects [{ steps: [...], latencies: [...] }]
 *   compact - boolean, render mini version (for overview page)
 *   onStepClick - optional callback (step, chainIndex, stepIndex) => void
 */

import { useMemo } from 'react';

/* ── Step type → display config ── */

const STEP_CONFIG = {
  llm:           { label: 'LLM',       icon: 'M', color: 'var(--chain-llm)',     bgClass: 'bg-[#2563eb]/12 border-[#2563eb]/30',     textClass: 'text-[#60a5fa]' },
  network:       { label: 'Network',   icon: 'N', color: 'var(--chain-net)',     bgClass: 'bg-[#2563eb]/12 border-[#2563eb]/30',     textClass: 'text-[#60a5fa]' },
  shell_exec:    { label: 'Shell',     icon: 'S', color: 'var(--chain-shell)',   bgClass: 'bg-[#ea580c]/12 border-[#ea580c]/30',     textClass: 'text-[#fb923c]' },
  exec:          { label: 'Process',   icon: 'P', color: 'var(--chain-shell)',   bgClass: 'bg-[#ea580c]/12 border-[#ea580c]/30',     textClass: 'text-[#fb923c]' },
  file_write:    { label: 'File',      icon: 'F', color: 'var(--chain-file)',    bgClass: 'bg-[#d97706]/12 border-[#d97706]/30',     textClass: 'text-[#fbbf24]' },
  file_delete:   { label: 'Delete',    icon: 'D', color: 'var(--chain-file)',    bgClass: 'bg-[#d97706]/12 border-[#d97706]/30',     textClass: 'text-[#fbbf24]' },
  file_modified: { label: 'File',      icon: 'F', color: 'var(--chain-file)',    bgClass: 'bg-[#d97706]/12 border-[#d97706]/30',     textClass: 'text-[#fbbf24]' },
  git:           { label: 'Git',       icon: 'G', color: 'var(--chain-git)',     bgClass: 'bg-[#16a34a]/12 border-[#16a34a]/30',     textClass: 'text-[#4ade80]' },
  sensitive:     { label: 'Cred',      icon: '!', color: 'var(--chain-cred)',    bgClass: 'bg-[#dc2626]/12 border-[#dc2626]/30',     textClass: 'text-[#f87171]' },
};

const DEFAULT_CONFIG = { label: '?', icon: '?', color: '#5a6478', bgClass: 'bg-detec-raised border-detec-edge', textClass: 'text-detec-ink-secondary' };

function getStepConfig(type) {
  const t = (type || '').trim().toLowerCase();
  return STEP_CONFIG[t] || DEFAULT_CONFIG;
}

/* ── Connector line between nodes ── */

function Connector({ latencyMs, compact }) {
  if (compact) {
    return (
      <div className="flex items-center px-0.5 shrink-0">
        <div className="w-3 h-px bg-detec-edge-emphasis" />
        <div className="w-0 h-0 border-t-[3px] border-t-transparent border-b-[3px] border-b-transparent border-l-[4px] border-l-detec-edge-emphasis" />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-0 shrink-0 min-w-[40px]">
      <div className="flex-1 relative flex items-center">
        <div className="w-full h-px bg-detec-edge-emphasis" />
        {latencyMs != null && (
          <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-data-xs font-data text-detec-ink-tertiary whitespace-nowrap">
            {latencyMs >= 1000 ? `${(latencyMs / 1000).toFixed(1)}s` : `${latencyMs}ms`}
          </span>
        )}
      </div>
      <div className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[5px] border-l-detec-edge-emphasis shrink-0" />
    </div>
  );
}

/* ── Single chain node ── */

function ChainNode({ type, detail, compact, onClick }) {
  const cfg = getStepConfig(type);

  if (compact) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-detec border ${cfg.bgClass} transition-colors hover:brightness-125 cursor-default`}
        title={`${cfg.label}${detail ? `: ${detail}` : ''}`}
      >
        <span className={`text-data-xs font-data font-bold ${cfg.textClass} leading-none`}>{cfg.icon}</span>
        <span className={`text-data-xs font-data ${cfg.textClass} leading-none`}>{cfg.label}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex flex-col items-start px-3 py-2 rounded-detec-md border ${cfg.bgClass} transition-colors hover:brightness-125 min-w-[100px] max-w-[200px] cursor-default`}
    >
      <div className="flex items-center gap-1.5">
        <span className={`w-5 h-5 rounded-detec flex items-center justify-center text-data-xs font-bold ${cfg.textClass} bg-black/20 shrink-0`}>
          {cfg.icon}
        </span>
        <span className={`text-data-sm font-data font-medium ${cfg.textClass} leading-tight`}>{cfg.label}</span>
      </div>
      {detail && (
        <span className="text-data-xs font-data text-detec-ink-tertiary mt-1 truncate w-full text-left" title={detail}>
          {detail}
        </span>
      )}
    </button>
  );
}

/* ── Parse chain strings into structured data ── */

function parseChains(chains) {
  if (!chains || !Array.isArray(chains) || chains.length === 0) return [];

  return chains.map(chain => {
    // Already structured: { steps: [...], latencies: [...] }
    if (typeof chain === 'object' && chain.steps) {
      return {
        steps: chain.steps.map(s => typeof s === 'string' ? { type: s } : s),
        latencies: chain.latencies || [],
      };
    }

    // String format: "llm -> shell_exec -> file_write -> git"
    if (typeof chain === 'string') {
      const parts = chain.split(/\s*->\s*/).map(s => s.trim()).filter(Boolean);
      return {
        steps: parts.map(p => ({ type: p })),
        latencies: [],
      };
    }

    return { steps: [], latencies: [] };
  }).filter(c => c.steps.length > 0);
}

/* ── Main component ── */

export default function BehaviorChainTimeline({ chains, compact = false, onStepClick }) {
  const parsed = useMemo(() => parseChains(chains), [chains]);

  if (parsed.length === 0) {
    return (
      <p className="text-data-sm font-data text-detec-ink-tertiary">No behavior chains detected</p>
    );
  }

  return (
    <div className="space-y-3" role="list" aria-label="Behavioral detection chains">
      {parsed.map((chain, chainIdx) => (
        <div
          key={chainIdx}
          role="listitem"
          className={`flex items-center flex-wrap gap-y-2 ${compact ? 'gap-x-0' : 'gap-x-0'} ${
            compact ? 'py-1' : 'py-2 px-3 rounded-detec-md border border-detec-edge-subtle bg-detec-surface/40'
          }`}
        >
          {/* Chain index badge (non-compact only) */}
          {!compact && parsed.length > 1 && (
            <span className="text-data-xs font-data text-detec-ink-tertiary mr-2 shrink-0">
              #{chainIdx + 1}
            </span>
          )}

          {chain.steps.map((step, stepIdx) => (
            <div key={stepIdx} className="inline-flex items-center">
              <ChainNode
                type={step.type}
                detail={step.detail}
                compact={compact}
                onClick={onStepClick ? () => onStepClick(step, chainIdx, stepIdx) : undefined}
              />
              {stepIdx < chain.steps.length - 1 && (
                <Connector
                  latencyMs={chain.latencies?.[stepIdx]}
                  compact={compact}
                />
              )}
            </div>
          ))}

          {/* Chain detection rule badge */}
          {chain.ruleId && !compact && (
            <span className="ml-auto text-data-xs font-data text-detec-ink-tertiary border border-detec-edge rounded-detec px-1.5 py-0.5 shrink-0">
              {chain.ruleId}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
