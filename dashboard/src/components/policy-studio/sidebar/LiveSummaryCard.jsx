/**
 * Live summary of current draft: name, severity, outcome, source, scope.
 */
import { ENDPOINT_SOURCES } from '../sources';

const SCOPE_LABELS = {
  source_code: 'Source code',
  credentials: 'Credentials',
  customer_data: 'Customer data',
  internal_docs: 'Internal docs',
  system_files: 'System files',
  pii: 'PII',
};

export default function LiveSummaryCard({ draft }) {
  const b = draft?.basics ?? {};
  const sourceId = draft?.source?.connectors?.[0] ?? draft?.source?.category ?? null;
  const source = ENDPOINT_SOURCES.find((s) => s.id === sourceId);
  const assets = draft?.scope?.assets ?? [];
  const scopeLabels = assets.map((id) => SCOPE_LABELS[id] || id);

  return (
    <div className="rounded-detec border border-detec-ui-border bg-detec-surface p-4">
      <h3 className="text-sm font-semibold text-detec-ink-primary mb-3">Summary</h3>
      <dl className="space-y-2 text-xs">
        <div>
          <dt className="text-detec-ink-secondary">Name</dt>
          <dd className="text-detec-ink-primary font-medium">{b.name || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ink-secondary">Severity</dt>
          <dd className="text-detec-ink-primary">{b.severity || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ink-secondary">Outcome</dt>
          <dd className="text-detec-ink-primary">{b.outcome || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ink-secondary">Source</dt>
          <dd className="text-detec-ink-primary">{source?.name ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ink-secondary">Scope</dt>
          <dd className="text-detec-ink-primary">{scopeLabels.length ? scopeLabels.join(', ') : '—'}</dd>
        </div>
      </dl>
    </div>
  );
}
