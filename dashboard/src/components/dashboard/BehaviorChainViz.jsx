import { useMemo } from 'react';

const STEP_LABELS = {
  llm: 'LLM call',
  shell_exec: 'Shell execution',
  exec: 'Process exec',
  file_write: 'File write',
  file_delete: 'File delete',
  network: 'Network / outbound',
  git: 'Git operation',
};

function stepLabel(step) {
  const t = (step || '').trim();
  return STEP_LABELS[t] || t || '—';
}

export default function BehaviorChainViz({ chains }) {
  const parsed = useMemo(() => {
    if (!chains || !Array.isArray(chains) || chains.length === 0) return [];
    return chains.map(chainStr => {
      const steps = (chainStr || '').split(/\s*->\s*/).map(s => s.trim()).filter(Boolean);
      return steps;
    });
  }, [chains]);

  if (parsed.length === 0) {
    return (
      <p className="text-sm text-detec-ui-muted">No behavior chains</p>
    );
  }

  return (
    <div className="space-y-4" aria-label="Behavior chains">
      {parsed.map((steps, chainIdx) => (
        <div key={chainIdx} className="flex flex-wrap items-center gap-1">
          {steps.map((step, stepIdx) => (
            <span key={stepIdx} className="inline-flex items-center gap-1">
              <span className="px-2 py-1 rounded bg-detec-slate-200/80 text-detec-ui-text text-xs font-medium">
                {stepLabel(step)}
              </span>
              {stepIdx < steps.length - 1 && (
                <span className="text-detec-ui-muted" aria-hidden="true">→</span>
              )}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
