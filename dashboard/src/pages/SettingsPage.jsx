import { useState, useEffect, useCallback } from 'react';
import { fetchWebhooks, fetchWebhookTemplates, createWebhook, createWebhookFromTemplate, updateWebhook, deleteWebhook, testWebhook, fetchAllowList, addAllowListEntry, deleteAllowListEntry, updateTenantPosture, fetchPostureSummary, fetchDisabledServices, restoreServices } from '../lib/api';
import useAuth from '../hooks/useAuth';

const EVENT_TYPES = [
  'enforcement.block',
  'enforcement.approval_required',
  'enforcement.warn',
  'enforcement.allow',
  'tool.detected',
  'tool.removed',
];

export default function SettingsPage() {
  const { user } = useAuth();

  const canManageWebhooks = user?.role === 'owner' || user?.role === 'admin';

  return (
    <div className="space-y-6 min-w-0">
      <h1 className="text-xl sm:text-2xl font-bold text-detec-ink-primary">Settings</h1>

      <div className="max-w-2xl space-y-6 w-full">


        {canManageWebhooks && <WebhooksSection />}

        {canManageWebhooks && <TenantPostureSection />}

        {canManageWebhooks && <AllowListSection />}

        {canManageWebhooks && <DisabledServicesSection />}
      </div>
    </div>
  );
}

function WebhooksSection() {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);

  const loadWebhooks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWebhooks();
      setWebhooks(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadWebhooks(); }, [loadWebhooks]);

  const handleDelete = async (id) => {
    if (!confirm('Delete this webhook?')) return;
    try {
      await deleteWebhook(id);
      loadWebhooks();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleTest = async (id) => {
    try {
      const result = await testWebhook(id);
      if (result.success) {
        setError(null);
      } else {
        setError('Test delivery failed. Check the webhook URL.');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggle = async (webhook) => {
    try {
      await updateWebhook(webhook.id, { is_active: !webhook.is_active });
      loadWebhooks();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
          Webhooks
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTemplateModal(true)}
            className="rounded-detec-md border border-detec-brand/50 px-3 py-1.5 text-xs font-medium text-detec-brand hover:bg-detec-brandHover/10 transition-colors"
          >
            Create from template
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="rounded-detec-md bg-detec-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-detec-brandHover transition-colors"
          >
            Add webhook
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-ink-secondary">Loading...</p>
      ) : webhooks.length === 0 ? (
        <div className="rounded-detec-md border border-dashed border-detec-ui-border bg-detec-slate-50 px-6 py-8 text-center">
          <p className="text-sm text-detec-ink-secondary">No webhooks configured.</p>
          <p className="text-xs text-detec-ink-secondary mt-1">Add a webhook to receive event notifications.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <div
              key={wh.id}
              className="rounded-detec-md border border-detec-ui-border/40 bg-detec-void/50 p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <code className="text-sm text-detec-ink-primary break-all">{wh.url}</code>
                  <div className="flex items-center gap-2 mt-1">
                    {wh.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-detec-ink-secondary">
                        <span className="h-1.5 w-1.5 rounded-full bg-detec-slate-200" />Paused
                      </span>
                    )}
                    {wh.events.length > 0 && (
                      <span className="text-xs text-detec-ink-secondary">
                        {wh.events.length} event type{wh.events.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    {wh.events.length === 0 && (
                      <span className="text-xs text-detec-ink-secondary">All events</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => handleTest(wh.id)}
                    className="rounded px-2 py-1 text-xs text-detec-ink-secondary hover:bg-detec-surface transition-colors"
                  >
                    Test
                  </button>
                  <button
                    onClick={() => handleToggle(wh)}
                    className="rounded px-2 py-1 text-xs text-detec-ink-secondary hover:bg-detec-surface transition-colors"
                  >
                    {wh.is_active ? 'Pause' : 'Resume'}
                  </button>
                  <button
                    onClick={() => handleDelete(wh.id)}
                    className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950/40 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <details className="group">
                <summary className="text-xs text-detec-ink-secondary cursor-pointer hover:text-detec-ink-secondary transition-colors">
                  Signing secret
                </summary>
                <code className="mt-1 block text-xs text-detec-ink-secondary break-all select-all">
                  {wh.secret}
                </code>
              </details>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <WebhookFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadWebhooks(); }}
        />
      )}

      {showTemplateModal && (
        <WebhookTemplateModal
          onClose={() => setShowTemplateModal(false)}
          onSaved={() => { setShowTemplateModal(false); loadWebhooks(); }}
          onError={(msg) => setError(msg)}
        />
      )}
    </div>
  );
}


function WebhookTemplateModal({ onClose, onSaved, onError }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [config, setConfig] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setFormError(null);
      try {
        const data = await fetchWebhookTemplates();
        if (!cancelled) setTemplates(data || []);
      } catch (err) {
        if (!cancelled) setFormError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const handleSelectTemplate = (t) => {
    setSelectedTemplate(t);
    const initial = {};
    for (const f of t.config_fields || []) {
      initial[f.key] = f.default || '';
    }
    setConfig(initial);
    setFormError(null);
  };

  const handleConfigChange = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTemplate) return;
    setFormError(null);
    const required = (selectedTemplate.config_fields || []).filter((f) => f.required);
    for (const f of required) {
      if (!(config[f.key] || '').trim()) {
        setFormError(`${f.label} is required`);
        return;
      }
    }
    setSubmitting(true);
    try {
      await createWebhookFromTemplate(selectedTemplate.id, config);
      onSaved();
    } catch (err) {
      setFormError(err.message);
      onError?.(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-detec-md border border-detec-ui-border bg-detec-void p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-ink-primary mb-4">Create Webhook from Template</h2>

        {loading ? (
          <p className="text-sm text-detec-ink-secondary">Loading templates...</p>
        ) : !selectedTemplate ? (
          <div className="space-y-2">
            <p className="text-xs text-detec-ink-secondary mb-3">Choose a SIEM or integration template:</p>
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelectTemplate(t)}
                className="w-full text-left rounded-detec-md border border-detec-ui-border bg-detec-surface/80 px-4 py-3 hover:border-detec-brand/30 hover:bg-detec-surface transition-colors"
              >
                <div className="font-medium text-detec-ink-primary">{t.name}</div>
                <div className="text-xs text-detec-ink-secondary mt-0.5">{t.description}</div>
              </button>
            ))}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-detec-ink-primary">{selectedTemplate.name}</h3>
              <button
                type="button"
                onClick={() => setSelectedTemplate(null)}
                className="text-xs text-detec-ink-secondary hover:text-detec-ink-primary"
              >
                Change template
              </button>
            </div>
            <p className="text-xs text-detec-ink-secondary">{selectedTemplate.description}</p>

            <div className="space-y-3">
              {(selectedTemplate.config_fields || []).map((f) => (
                <label key={f.key} className="block">
                  <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">
                    {f.label}
                    {f.required && <span className="text-red-400 ml-0.5">*</span>}
                  </span>
                  <input
                    type={f.secret ? 'password' : 'text'}
                    value={config[f.key] ?? ''}
                    onChange={(e) => handleConfigChange(f.key, e.target.value)}
                    placeholder={f.placeholder || f.default || ''}
                    spellCheck={false}
                    className="mt-1 w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary font-mono placeholder:text-detec-ink-secondary focus:border-detec-brand focus:outline-none"
                  />
                </label>
              ))}
            </div>

            {formError && (
              <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-detec-md border border-detec-ui-border px-4 py-2 text-sm text-detec-ink-secondary hover:bg-detec-surface"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-detec-md bg-detec-brand px-4 py-2 text-sm font-medium text-white hover:bg-detec-brandHover disabled:opacity-50"
              >
                {submitting ? 'Creating...' : 'Create webhook'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}


const POSTURE_META = {
  passive: { label: 'Passive', color: 'bg-detec-slate-200/30 text-detec-ink-secondary', dot: 'bg-detec-slate-500' },
  audit:   { label: 'Audit',   color: 'bg-detec-amber-500/15 text-detec-amber-500', dot: 'bg-detec-amber-500' },
  active:  { label: 'Active',  color: 'bg-detec-enforce-block/15 text-detec-enforce-block', dot: 'bg-detec-enforce-block' },
};

const POSTURE_OPTIONS = [
  { value: 'passive', label: 'Passive', desc: 'Detect and report only' },
  { value: 'audit', label: 'Audit', desc: 'Log enforcement decisions without acting' },
  { value: 'active', label: 'Active', desc: 'Autonomous process termination', ownerOnly: true },
];

function TenantPostureSection() {
  const { user } = useAuth();
  const isOwner = user?.role === 'owner';

  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPosture, setSelectedPosture] = useState('passive');
  const [selectedThreshold, setSelectedThreshold] = useState(0.75);
  const [applyToAll, setApplyToAll] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPostureSummary();
      setSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 6000);
    return () => clearTimeout(t);
  }, [feedback]);

  function handleSave() {
    if (selectedPosture === 'active') {
      setShowConfirm(true);
      setConfirmInput('');
    } else {
      doSave();
    }
  }

  async function doSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateTenantPosture({
        enforcement_posture: selectedPosture,
        auto_enforce_threshold: selectedThreshold,
      });
      setFeedback({
        type: 'success',
        msg: `Tenant posture set to ${selectedPosture}. ${result.updated} endpoint${result.updated !== 1 ? 's' : ''} updated.`,
      });
      setShowConfirm(false);
      setApplyToAll(false);
      loadSummary();
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Failed to update tenant posture' });
    } finally {
      setSaving(false);
    }
  }

  const showThreshold = selectedPosture === 'audit' || selectedPosture === 'active';

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
        Enforcement Posture
      </h2>
      <p className="text-xs text-detec-ink-secondary">
        Set the default enforcement posture for all endpoints in this tenant.
        New endpoints inherit this posture on registration.
      </p>

      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {feedback && (
        <div className={`text-xs px-3 py-1.5 rounded detec-toast-enter ${
          feedback.type === 'success'
            ? 'bg-detec-teal-500/10 text-detec-teal-500 border border-detec-teal-500/20'
            : 'bg-detec-enforce-block/10 text-detec-enforce-block border border-red-800/50'
        }`}>
          {feedback.msg}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-detec-ink-secondary">Loading...</p>
      ) : (
        <>
          {/* Current posture distribution */}
          {summary && (
            <div className="flex gap-3 text-xs">
              {['passive', 'audit', 'active'].map((p) => {
                const meta = POSTURE_META[p];
                const count = summary[p] || 0;
                return (
                  <div key={p} className={`flex items-center gap-1.5 rounded px-2.5 py-1 ${meta.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    <span>{meta.label}</span>
                    <span className="font-mono font-semibold">{count}</span>
                  </div>
                );
              })}
              <span className="text-detec-ink-secondary self-center ml-1">
                {summary.total} endpoint{summary.total !== 1 ? 's' : ''} total
              </span>
            </div>
          )}

          {/* Three-state posture selector */}
          <div className="flex flex-col sm:flex-row gap-2">
            {POSTURE_OPTIONS.map((opt) => {
              const selected = selectedPosture === opt.value;
              const disabled = opt.ownerOnly && !isOwner;
              const meta = POSTURE_META[opt.value];
              return (
                <button
                  key={opt.value}
                  disabled={disabled}
                  onClick={() => !disabled && setSelectedPosture(opt.value)}
                  className={`flex-1 rounded-detec-md border px-3 py-2 text-left transition-all ${
                    selected
                      ? `border-detec-brand/50 ${meta.color} ring-1 ring-detec-ui-accent/30`
                      : disabled
                        ? 'border-detec-ui-border/50 bg-detec-slate-50 opacity-40 cursor-not-allowed'
                        : 'border-detec-ui-border bg-detec-surface/80 hover:border-detec-ui-border cursor-pointer'
                  }`}
                  title={disabled ? 'Owner role required for Active posture' : ''}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${selected ? meta.dot : 'bg-detec-slate-200'}`} />
                    <span className={`text-sm font-medium ${selected ? '' : 'text-detec-ink-secondary'}`}>{opt.label}</span>
                  </div>
                  <p className="text-xs text-detec-ink-secondary mt-1">{opt.desc}</p>
                  {disabled && (
                    <p className="text-xs text-detec-enforce-warn mt-1">Owner only</p>
                  )}
                </button>
              );
            })}
          </div>

          {/* Threshold slider */}
          {showThreshold && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-detec-ink-secondary">
                  Auto-enforce threshold
                </label>
                <span className="text-sm font-mono text-detec-ink-primary">{selectedThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.50"
                max="1.00"
                step="0.05"
                value={selectedThreshold}
                onChange={(e) => setSelectedThreshold(parseFloat(e.target.value))}
                className="w-full accent-detec-brand cursor-pointer"
              />
              <div className="flex justify-between text-xs text-detec-ink-secondary">
                <span>0.50 (aggressive)</span>
                <span>1.00 (conservative)</span>
              </div>
            </div>
          )}

          {/* Apply to all checkbox */}
          <label className="flex items-start gap-2.5 cursor-pointer group">
            <input
              type="checkbox"
              checked={applyToAll}
              onChange={(e) => setApplyToAll(e.target.checked)}
              className="mt-0.5 rounded border-detec-ui-border bg-detec-void text-detec-brand focus:ring-detec-brand/30"
            />
            <div>
              <span className="text-sm text-detec-ink-primary group-hover:text-detec-ink-primary transition-colors">
                Apply to all existing endpoints
              </span>
              {summary && (
                <p className="text-xs text-detec-ink-secondary mt-0.5">
                  Updates {summary.total} existing endpoint{summary.total !== 1 ? 's' : ''} to the selected posture and threshold
                </p>
              )}
            </div>
          </label>

          {/* Save */}
          <div className="flex items-center gap-3">
            <button
              disabled={!applyToAll || saving}
              onClick={handleSave}
              className={`px-4 py-2 text-sm font-medium rounded-detec-md transition-colors ${
                applyToAll && !saving
                  ? 'bg-detec-brand hover:bg-detec-brand text-white cursor-pointer'
                  : 'bg-detec-slate-200 text-detec-ink-secondary cursor-not-allowed'
              }`}
            >
              {saving ? 'Saving...' : 'Save Enforcement Defaults'}
            </button>
            {!applyToAll && (
              <span className="text-xs text-detec-ink-secondary">
                Check "Apply to all" to enable saving
              </span>
            )}
          </div>
        </>
      )}

      {showConfirm && (
        <ConfirmActiveTenantModal
          endpointCount={summary?.total || 0}
          threshold={selectedThreshold}
          confirmInput={confirmInput}
          onInputChange={setConfirmInput}
          onConfirm={doSave}
          onCancel={() => setShowConfirm(false)}
          saving={saving}
        />
      )}
    </div>
  );
}

const CONFIRM_PHRASE = 'ENABLE ACTIVE';

function ConfirmActiveTenantModal({ endpointCount, threshold, confirmInput, onInputChange, onConfirm, onCancel, saving }) {
  const confirmed = confirmInput === CONFIRM_PHRASE;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onCancel}>
      <div
        className="w-full max-w-lg rounded-detec-md border border-detec-ui-border bg-detec-void p-4 sm:p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-detec-ink-primary">Enable Active Enforcement for All Endpoints</h2>

        <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-block/10 p-4 text-sm text-detec-enforce-block space-y-2">
          <p className="font-semibold">This is a destructive, tenant-wide action.</p>
          <p>
            Active enforcement enables <strong>autonomous process termination</strong> on
            all <strong>{endpointCount}</strong> endpoint{endpointCount !== 1 ? 's' : ''} in
            this tenant. Agents will automatically kill processes that exceed the confidence
            threshold of <strong>{threshold.toFixed(2)}</strong> without human approval.
          </p>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-detec-ink-secondary">Endpoints affected</span>
              <p className="text-detec-ink-primary font-mono">{endpointCount}</p>
            </div>
            <div>
              <span className="text-detec-ink-secondary">Threshold</span>
              <p className="text-detec-ink-primary font-mono">{threshold.toFixed(2)}</p>
            </div>
          </div>

          <div>
            <label className="block text-sm text-detec-ink-secondary mb-1.5">
              Type <span className="font-mono text-detec-ink-primary">{CONFIRM_PHRASE}</span> to confirm
            </label>
            <input
              type="text"
              value={confirmInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder={CONFIRM_PHRASE}
              autoFocus
              className="w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary placeholder:text-detec-ink-secondary focus:outline-none focus:ring-1 focus:ring-detec-enforce-block/50"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-detec-md text-detec-ink-secondary hover:text-detec-ink-primary transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={!confirmed || saving}
            onClick={onConfirm}
            className={`text-sm px-4 py-1.5 rounded-detec-md font-medium transition-colors ${
              confirmed && !saving
                ? 'bg-detec-enforce-block text-white hover:bg-red-600 cursor-pointer'
                : 'bg-detec-slate-200 text-detec-ink-secondary cursor-not-allowed'
            }`}
          >
            {saving ? 'Enabling...' : 'Enable Active Enforcement'}
          </button>
        </div>
      </div>
    </div>
  );
}


const PATTERN_TYPES = [
  { value: 'name', label: 'Name' },
  { value: 'path', label: 'Path' },
  { value: 'hash', label: 'Hash' },
];

function AllowListSection() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAllowList();
      setEntries(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleDelete = async (id, pattern) => {
    if (!confirm(`Remove "${pattern}" from the allow list?`)) return;
    try {
      await deleteAllowListEntry(id);
      loadEntries();
    } catch (err) {
      setError(err.message);
    }
  };

  const fmtDate = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
          Enforcement Allow List
        </h2>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-detec-md bg-detec-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-detec-brandHover transition-colors"
        >
          Add entry
        </button>
      </div>

      <p className="text-xs text-detec-ink-secondary">
        Tools matching an allow-list entry are exempt from enforcement actions regardless of posture or policy.
      </p>

      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-ink-secondary">Loading...</p>
      ) : entries.length === 0 ? (
        <div className="rounded-detec-md border border-dashed border-detec-ui-border bg-detec-slate-50 px-6 py-8 text-center">
          <p className="text-sm text-detec-ink-secondary">No allow-list entries.</p>
          <p className="text-xs text-detec-ink-secondary mt-1">Add an entry to exempt specific tools from enforcement.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-detec-ui-border/40 text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">
                <th className="pb-2 pr-4">Pattern</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Description</th>
                <th className="pb-2 pr-4">Created by</th>
                <th className="pb-2 pr-4">Created</th>
                <th className="pb-2 w-16" />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-detec-ui-border/20">
                  <td className="py-2.5 pr-4">
                    <code className="text-xs text-detec-ink-primary break-all">{entry.pattern}</code>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="inline-block rounded bg-detec-slate-100 px-2 py-0.5 text-xs text-detec-ink-secondary">
                      {entry.pattern_type}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-ink-secondary">
                    {entry.description || <span className="text-detec-ink-secondary italic">none</span>}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-ink-secondary">
                    {entry.created_by || <span className="text-detec-ink-secondary">unknown</span>}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-ink-secondary whitespace-nowrap">
                    {fmtDate(entry.created_at)}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      onClick={() => handleDelete(entry.id, entry.pattern)}
                      className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950/40 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <AllowListFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadEntries(); }}
        />
      )}
    </div>
  );
}

function AllowListFormModal({ onClose, onSaved }) {
  const [pattern, setPattern] = useState('');
  const [patternType, setPatternType] = useState('name');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    const trimmed = pattern.trim();
    if (!trimmed) { setFormError('Pattern is required'); return; }
    if (trimmed.length < 3) { setFormError('Pattern must be at least 3 characters'); return; }

    setSubmitting(true);
    try {
      await addAllowListEntry({
        pattern: trimmed,
        pattern_type: patternType,
        description: description.trim() || undefined,
      });
      onSaved();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-detec-md border border-detec-ui-border bg-detec-void p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-ink-primary mb-4">Add Allow-List Entry</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Pattern</label>
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder="e.g. ollama, /usr/local/bin/ollama, sha256:abc..."
              required
              spellCheck={false}
              className="w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary font-mono focus:border-detec-brand focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Match Type</label>
            <select
              value={patternType}
              onChange={(e) => setPatternType(e.target.value)}
              className="w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary focus:border-detec-brand focus:outline-none"
            >
              {PATTERN_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>{pt.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-detec-ink-secondary">
              {patternType === 'name' && 'Match by tool or process name (e.g. "ollama")'}
              {patternType === 'path' && 'Match by full executable path (e.g. "/usr/local/bin/ollama")'}
              {patternType === 'hash' && 'Match by binary SHA-256 hash'}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary mb-1">
              Description <span className="font-normal text-detec-ink-secondary">(optional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Why this tool is exempt"
              className="w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary focus:border-detec-brand focus:outline-none"
            />
          </div>

          {formError && (
            <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-detec-md border border-detec-ui-border px-4 py-2 text-sm text-detec-ink-secondary hover:bg-detec-surface"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-detec-md bg-detec-brand px-4 py-2 text-sm font-medium text-white hover:bg-detec-brandHover disabled:opacity-50"
            >
              {submitting ? 'Adding...' : 'Add entry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DisabledServicesSection() {
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [restoring, setRestoring] = useState({});
  const [feedback, setFeedback] = useState(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchDisabledServices();
      setEndpoints(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRestore = async (endpointId, serviceId, unitName) => {
    if (!confirm(`Restore service "${unitName}" on this endpoint?`)) return;
    setRestoring((prev) => ({ ...prev, [serviceId]: true }));
    setFeedback(null);
    try {
      await restoreServices(endpointId, [serviceId]);
      setFeedback({ type: 'success', text: `Restore queued for ${unitName}. The agent will re-enable it on the next heartbeat.` });
      loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setRestoring((prev) => ({ ...prev, [serviceId]: false }));
    }
  };

  const handleRestoreAll = async (endpointId, hostname) => {
    if (!confirm(`Restore all disabled services on ${hostname}?`)) return;
    setRestoring((prev) => ({ ...prev, [endpointId]: true }));
    setFeedback(null);
    try {
      const result = await restoreServices(endpointId);
      setFeedback({ type: 'success', text: `${result.queued} service(s) queued for restoration on ${hostname}.` });
      loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setRestoring((prev) => ({ ...prev, [endpointId]: false }));
    }
  };

  const fmtDate = (ts) => {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const totalServices = endpoints.reduce((sum, ep) => sum + (ep.disabled_services?.length || 0), 0);

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
          Disabled Services
        </h2>
        {totalServices > 0 && (
          <span className="rounded-full bg-detec-enforce-block/15 px-2.5 py-0.5 text-xs font-medium text-detec-enforce-block">
            {totalServices} disabled
          </span>
        )}
      </div>

      <p className="text-xs text-detec-ink-secondary">
        Services disabled by anti-resurrection escalation (repeated enforcement kills). Restoring re-enables the service unit on the endpoint.
      </p>

      {feedback && (
        <div className={`rounded-detec-md border px-3 py-2 text-xs ${
          feedback.type === 'success'
            ? 'border-detec-teal-500/30 bg-detec-teal-900/20 text-detec-teal-400'
            : 'border-red-800/50 bg-red-950/30 text-red-400'
        }`}>
          {feedback.text}
        </div>
      )}

      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-ink-secondary">Loading...</p>
      ) : endpoints.length === 0 ? (
        <div className="rounded-detec-md border border-dashed border-detec-ui-border bg-detec-slate-50 px-6 py-8 text-center">
          <p className="text-sm text-detec-ink-secondary">No disabled services across any endpoints.</p>
          <p className="text-xs text-detec-ink-secondary mt-1">Services appear here when anti-resurrection escalation disables a systemd unit or launchd plist.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {endpoints.map((ep) => (
            <div key={ep.endpoint_id} className="rounded-detec-md border border-detec-ui-border/40 bg-detec-void/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-detec-ink-primary">{ep.hostname}</span>
                  <span className="text-xs text-detec-ink-secondary font-mono">{ep.endpoint_id.slice(0, 8)}</span>
                </div>
                {ep.disabled_services?.length > 1 && (
                  <button
                    onClick={() => handleRestoreAll(ep.endpoint_id, ep.hostname)}
                    disabled={restoring[ep.endpoint_id]}
                    className="rounded-detec-md border border-detec-teal-500/30 px-2.5 py-1 text-xs font-medium text-detec-teal-400 hover:bg-detec-teal-500/10 disabled:opacity-50 transition-colors"
                  >
                    {restoring[ep.endpoint_id] ? 'Queuing...' : 'Restore all'}
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-detec-ink-secondary border-b border-detec-ui-border/30">
                      <th className="text-left py-1.5 pr-3 font-medium">Unit</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Type</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Tool</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Disabled</th>
                      <th className="text-right py-1.5 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ep.disabled_services.map((svc) => (
                      <tr key={svc.service_id} className="border-b border-detec-ui-border/20 last:border-0">
                        <td className="py-2 pr-3 font-mono text-detec-ink-primary">{svc.unit_name}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                            svc.service_type === 'systemd'
                              ? 'bg-blue-500/15 text-blue-400'
                              : 'bg-purple-500/15 text-purple-400'
                          }`}>
                            {svc.service_type}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-detec-ink-secondary">{svc.tool_name || 'N/A'}</td>
                        <td className="py-2 pr-3 text-detec-ink-secondary">{fmtDate(svc.disabled_at)}</td>
                        <td className="py-2 text-right">
                          <button
                            onClick={() => handleRestore(ep.endpoint_id, svc.service_id, svc.unit_name)}
                            disabled={restoring[svc.service_id]}
                            className="rounded-detec-md bg-detec-teal-600 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-detec-teal-500 disabled:opacity-50 transition-colors"
                          >
                            {restoring[svc.service_id] ? 'Queuing...' : 'Restore'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function WebhookFormModal({ onClose, onSaved }) {
  const [url, setUrl] = useState('');
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const toggleEvent = (event) => {
    setSelectedEvents(prev =>
      prev.includes(event)
        ? prev.filter(e => e !== event)
        : [...prev, event]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!url.trim()) { setFormError('URL is required'); return; }

    setSubmitting(true);
    try {
      await createWebhook({ url: url.trim(), events: selectedEvents });
      onSaved();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-detec-md border border-detec-ui-border bg-detec-void p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-ink-primary mb-4">Add Webhook</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Endpoint URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/webhook"
              required
              className="w-full rounded-detec-md border border-detec-ui-border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary focus:border-detec-brand focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-ink-secondary mb-2">
              Event types <span className="font-normal text-detec-ink-secondary">(leave empty for all)</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {EVENT_TYPES.map((evt) => (
                <label
                  key={evt}
                  className="flex items-center gap-2 rounded-detec-md border border-detec-ui-border/40 bg-detec-surface/80 px-3 py-2 cursor-pointer hover:border-detec-brand/30 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(evt)}
                    onChange={() => toggleEvent(evt)}
                    className="rounded border-detec-ui-border bg-detec-void text-detec-brand focus:ring-detec-brand/30"
                  />
                  <span className="text-xs text-detec-ink-primary">{evt}</span>
                </label>
              ))}
            </div>
          </div>

          {formError && (
            <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-detec-md border border-detec-ui-border px-4 py-2 text-sm text-detec-ink-secondary hover:bg-detec-surface"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-detec-md bg-detec-brand px-4 py-2 text-sm font-medium text-white hover:bg-detec-brandHover disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create webhook'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
