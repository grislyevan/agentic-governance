/**
 * Policy Studio Step 2: Choose data source. data = draft.source (connectors[], category, tags).
 */

import { ENDPOINT_SOURCES } from '../sources';

export default function SourceStep({ data, onChange }) {
  const source = data || {};
  const selectedId = source.connectors?.[0] ?? source.category ?? null;

  const select = (id) => {
    onChange({ connectors: id ? [id] : [], category: id || '' });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-detec-ui-muted">
        Where should this policy look? Select one source. Future connectors (e.g. Microsoft 365, Google Workspace) will appear here when available.
      </p>
      <div className="grid gap-3">
        {ENDPOINT_SOURCES.map((s) => {
          const isSelected = selectedId === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => select(isSelected ? null : s.id)}
              className={`w-full text-left rounded-detec-md border p-4 transition-colors shadow-detec-sm ${
                isSelected
                  ? 'border-detec-ui-accent bg-detec-ui-accent/5 ring-1 ring-detec-ui-accent/30'
                  : 'border-detec-ui-border bg-detec-ui-surface hover:border-detec-slate-300'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-detec-slate-100 flex items-center justify-center shrink-0">
                  <span className="text-lg font-semibold text-detec-ui-muted">{s.name[0]}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-detec-ui-text">{s.name}</div>
                  <div className="text-sm text-detec-ui-muted mt-0.5">{s.description}</div>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {s.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs px-2 py-0.5 rounded bg-detec-slate-100 text-detec-ui-muted"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                {isSelected && (
                  <span className="text-detec-ui-accent shrink-0" aria-hidden="true">&#10003;</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <div className="pt-4 border-t border-detec-ui-border">
        <p className="text-xs text-detec-ui-muted font-medium uppercase tracking-wider">Coming later</p>
        <p className="text-sm text-detec-ui-muted mt-1">M365, Google Workspace, Datadog, GitHub cloud integrations</p>
      </div>
    </div>
  );
}
