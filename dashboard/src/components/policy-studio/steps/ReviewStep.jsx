/**
 * Policy Studio Step 5: Review. draft = full nested draft. Summary, then Save draft / Preview / Submit / Publish.
 */

import { ENDPOINT_SOURCES } from '../sources';

const SCOPE_LABELS = {
  source_code: 'Source code',
  credentials: 'Credentials / secrets',
  customer_data: 'Customer data',
  internal_docs: 'Internal documents',
  system_files: 'System files',
  pii: 'PII',
  file_access: 'File access',
  repo_actions: 'Repo actions',
  network_transmission: 'Network transmission',
  runtime_actions: 'Runtime actions',
};

export default function ReviewStep({ draft, onSaveDraft, onPublish, onPreviewMatches, saving }) {
  const b = draft?.basics ?? {};
  const sourceId = draft?.source?.connectors?.[0] ?? draft?.source?.category ?? null;
  const source = ENDPOINT_SOURCES.find((s) => s.id === sourceId);
  const assets = draft?.scope?.assets ?? [];
  const scopeLabels = assets.map((id) => SCOPE_LABELS[id] || id);

  return (
    <div className="space-y-6">
      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-detec-ui-text">Basics</h3>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-detec-ui-muted">Name</dt>
          <dd className="text-detec-ui-text">{b.name || '—'}</dd>
          <dt className="text-detec-ui-muted">Description</dt>
          <dd className="text-detec-ui-text">{b.description || '—'}</dd>
          <dt className="text-detec-ui-muted">Severity</dt>
          <dd className="text-detec-ui-text">{b.severity || '—'}</dd>
          <dt className="text-detec-ui-muted">Outcome</dt>
          <dd className="text-detec-ui-text">{b.outcome || '—'}</dd>
        </dl>
      </div>

      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Source</h3>
        <p className="text-sm text-detec-ui-text">{source?.name ?? '—'}</p>
      </div>

      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Scope</h3>
        <p className="text-sm text-detec-ui-text">{scopeLabels.length ? scopeLabels.join(', ') : '—'}</p>
      </div>

      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Rules</h3>
        <p className="text-sm text-detec-ui-text">{(draft?.rules?.mode || 'simple') === 'simple' ? 'Simple mode (derived from Basics and Scope)' : 'Advanced mode (custom JSON)'}</p>
      </div>

      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Explainability</h3>
        <ul className="text-sm text-detec-ui-muted list-disc list-inside space-y-1">
          <li>Signals evaluated from selected source and scope</li>
          <li>Trigger conditions based on rule definition</li>
          <li>Enforcement outcome: {b.outcome || 'warn'}</li>
        </ul>
      </div>

      <div className="rounded-detec-md border border-detec-ui-border bg-detec-slate-50/50 p-5 space-y-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Preview matches</h3>
        <p className="text-sm text-detec-ui-muted">Preview is not available yet. Use Save draft or Publish to continue.</p>
      </div>

      <div className="flex flex-wrap gap-3 pt-2">
        <button
          type="button"
          onClick={onSaveDraft}
          disabled={saving}
          className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm font-medium text-detec-ui-text hover:bg-detec-slate-100 disabled:opacity-50"
        >
          Save draft
        </button>
        <button
          type="button"
          onClick={onPreviewMatches}
          className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm font-medium text-detec-ui-muted hover:bg-detec-slate-100"
        >
          Preview matches
        </button>
        <button
          type="button"
          onClick={() => onPublish(false)}
          disabled={saving}
          className="h-10 px-4 rounded-detec border border-detec-ui-accent text-sm font-medium text-detec-ui-accent hover:bg-detec-ui-accent/10 disabled:opacity-50"
        >
          Submit for review
        </button>
        <button
          type="button"
          onClick={() => onPublish(true)}
          disabled={saving}
          className="h-10 px-4 rounded-detec bg-detec-ui-accent text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
        >
          {saving ? 'Publishing...' : 'Publish'}
        </button>
      </div>
    </div>
  );
}
