/**
 * Policy Studio Step 3: Scope. data = draft.scope (assets[], subjects[], sensitivity[]).
 * Data at risk + optional activity targets; internal mapping to API params only.
 */

import { SCOPE_CHIPS } from '../sources';

const DATA_AT_RISK = [
  { id: 'source_code', label: 'Source code' },
  { id: 'credentials', label: 'Credentials / secrets' },
  { id: 'customer_data', label: 'Customer data' },
  { id: 'internal_docs', label: 'Internal documents' },
  { id: 'system_files', label: 'System files' },
  { id: 'pii', label: 'PII' },
];

const ACTIVITY_TARGETS = [
  { id: 'file_access', label: 'File access' },
  { id: 'repo_actions', label: 'Repo actions' },
  { id: 'network_transmission', label: 'Network transmission' },
  { id: 'runtime_actions', label: 'Runtime actions' },
];

const SENSITIVITY = [
  { id: 'low', label: 'Low' },
  { id: 'medium', label: 'Medium' },
  { id: 'high', label: 'High' },
  { id: 'critical', label: 'Critical' },
];

export default function ScopeStep({ data, onChange }) {
  const scope = data || {};
  const assets = scope.assets || [];
  const subjects = scope.subjects || [];
  const sensitivity = scope.sensitivity || [];

  const toggle = (listKey, id) => {
    const list = listKey === 'assets' ? assets : listKey === 'subjects' ? subjects : sensitivity;
    const next = list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
    onChange({ [listKey]: next });
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-detec-ink-secondary">
        What are you trying to protect or govern? Select data types and optional activity targets.
      </p>

      <section>
        <h4 className="text-sm font-semibold text-detec-ink-primary mb-2">Data at risk</h4>
        <div className="flex flex-wrap gap-2">
          {DATA_AT_RISK.map((chip) => {
            const isSelected = assets.includes(chip.id);
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => toggle('assets', chip.id)}
                className={`px-4 py-2 rounded-detec text-sm font-medium transition-colors ${
                  isSelected
                    ? 'bg-detec-brand/10 border border-detec-brand text-detec-ink-primary'
                    : 'bg-white border border-detec-ui-border text-detec-ink-primary hover:border-detec-slate-300'
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h4 className="text-sm font-semibold text-detec-ink-primary mb-2">Activity targets</h4>
        <div className="flex flex-wrap gap-2">
          {ACTIVITY_TARGETS.map((chip) => {
            const isSelected = subjects.includes(chip.id);
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => toggle('subjects', chip.id)}
                className={`px-4 py-2 rounded-detec text-sm font-medium transition-colors ${
                  isSelected
                    ? 'bg-detec-brand/10 border border-detec-brand text-detec-ink-primary'
                    : 'bg-white border border-detec-ui-border text-detec-ink-primary hover:border-detec-slate-300'
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h4 className="text-sm font-semibold text-detec-ink-primary mb-2">Sensitivity</h4>
        <div className="flex flex-wrap gap-2">
          {SENSITIVITY.map((chip) => {
            const isSelected = sensitivity.includes(chip.id);
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => toggle('sensitivity', chip.id)}
                className={`px-4 py-2 rounded-detec text-sm font-medium transition-colors ${
                  isSelected
                    ? 'bg-detec-brand/10 border border-detec-brand text-detec-ink-primary'
                    : 'bg-white border border-detec-ui-border text-detec-ink-primary hover:border-detec-slate-300'
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
