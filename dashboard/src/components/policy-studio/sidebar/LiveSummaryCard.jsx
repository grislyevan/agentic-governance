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
    <div className="rounded-detec border border-detec-ui-border bg-detec-ui-surface p-4 shadow-detec-sm">
      <h3 className="text-sm font-semibold text-detec-ui-text mb-3">Summary</h3>
      <dl className="space-y-2 text-xs">
        <div>
          <dt className="text-detec-ui-muted">Name</dt>
          <dd className="text-detec-ui-text font-medium">{b.name || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ui-muted">Severity</dt>
          <dd className="text-detec-ui-text">{b.severity || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ui-muted">Outcome</dt>
          <dd className="text-detec-ui-text">{b.outcome || '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ui-muted">Source</dt>
          <dd className="text-detec-ui-text">{source?.name ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-detec-ui-muted">Scope</dt>
          <dd className="text-detec-ui-text">{scopeLabels.length ? scopeLabels.join(', ') : '—'}</dd>
        </div>
      </dl>
    </div>
  );
}
