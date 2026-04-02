import { useEffect, useState } from 'react';
import { fetchCurrentTenant, updateTenant, rotateAgentKey } from '../lib/api';

export default function OrgSettingsPage() {
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Agent key rotation state
  const [showRotateConfirm, setShowRotateConfirm] = useState(false);
  const [rotateResult, setRotateResult] = useState(null); // { agent_key, prefix, rotated_at }
  const [rotateLoading, setRotateLoading] = useState(false);
  const [rotateError, setRotateError] = useState(null);
  const [keyCopied, setKeyCopied] = useState(false);

  useEffect(() => {
    fetchCurrentTenant()
      .then(t => { setTenant(t); setNameInput(t.name); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateTenant(tenant.id, { name: nameInput });
      setTenant(prev => ({ ...prev, name: updated.name, slug: updated.slug }));
      setEditing(false);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const handleRotateKey = async () => {
    setRotateLoading(true);
    setRotateError(null);
    try {
      const result = await rotateAgentKey();
      setRotateResult(result);
      setShowRotateConfirm(false);
    } catch (e) {
      setRotateError(e.message || 'Failed to rotate key');
    } finally {
      setRotateLoading(false);
    }
  };

  const handleCopyKey = async () => {
    if (!rotateResult?.agent_key) return;
    try {
      await navigator.clipboard.writeText(rotateResult.agent_key);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 2000);
    } catch {
      // fallback: select the text
    }
  };

  const handleDismissResult = () => {
    setRotateResult(null);
    setKeyCopied(false);
  };

  if (loading) return <div className="p-8 text-detec-ink-secondary">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">{error}</div>;

  const isOwner = tenant.role === 'owner';

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-xl font-semibold text-detec-ink-primary mb-6">Organization Settings</h1>
      <div className="bg-detec-surface border border-detec-ui-border rounded-detec-md p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Organization name</label>
          {editing ? (
            <input
              id="org-name-input"
              aria-label="Org name"
              className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ink-primary focus:outline-none focus:ring-1 focus:ring-detec-brand"
              value={nameInput}
              onChange={e => setNameInput(e.target.value)}
            />
          ) : (
            <p className="text-sm text-detec-ink-primary">{tenant.name}</p>
          )}
        </div>
        <div>
          <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Slug</label>
          <p className="text-sm font-mono text-detec-ink-secondary">{tenant.slug}</p>
        </div>
        <div>
          <label className="block text-xs font-medium text-detec-ink-secondary mb-1">Subscription tier</label>
          <p className="text-sm text-detec-ink-primary capitalize">{tenant.subscription_tier || 'free'}</p>
        </div>
        <div className="flex gap-6 pt-2">
          <div>
            <p className="text-xs text-detec-ink-secondary">Members</p>
            <p className="text-lg font-semibold text-detec-ink-primary">{tenant.member_count}</p>
          </div>
          <div>
            <p className="text-xs text-detec-ink-secondary">Endpoints</p>
            <p className="text-lg font-semibold text-detec-ink-primary">{tenant.endpoint_count}</p>
          </div>
        </div>
        {isOwner && !editing && (
          <button
            className="mt-2 px-4 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ink-primary hover:bg-detec-slate-100 transition-colors"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        )}
        {editing && (
          <div className="flex gap-2 mt-2">
            <button
              className="px-4 py-1.5 text-sm rounded bg-detec-brand text-white hover:opacity-90 transition-opacity disabled:opacity-50"
              onClick={handleSave}
              disabled={saving || !nameInput.trim()}
            >
              {saving ? 'Saving\u2026' : 'Save'}
            </button>
            <button
              className="px-4 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ink-secondary hover:bg-detec-slate-100 transition-colors"
              onClick={() => { setEditing(false); setNameInput(tenant.name); setSaveError(null); }}
            >
              Cancel
            </button>
            {saveError && <p className="text-xs text-red-600 self-center">{saveError}</p>}
          </div>
        )}
      </div>
      {!isOwner && (
        <p className="mt-4 text-xs text-detec-ink-secondary">Only the organization owner can edit these settings.</p>
      )}

      {/* Agent Key section */}
      <div className="mt-6 bg-detec-surface border border-detec-ui-border rounded-detec-md p-6">
        <h2 className="text-sm font-semibold text-detec-ink-primary mb-1">Agent Key</h2>
        <p className="text-xs text-detec-ink-secondary mb-4">
          The agent key authenticates endpoint agents to this server. Rotating it immediately
          invalidates all existing agent connections.
        </p>

        {/* Post-rotation result: show new key once */}
        {rotateResult && (
          <div className="mb-4 rounded-detec-md border border-amber-400 bg-amber-50 dark:bg-amber-950 p-4 space-y-3">
            <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">
              Store this key securely &mdash; it will not be shown again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 block text-xs font-mono bg-white dark:bg-detec-bg border border-detec-ui-border rounded px-3 py-2 text-detec-ink-primary break-all select-all">
                {rotateResult.agent_key}
              </code>
              <button
                onClick={handleCopyKey}
                className="shrink-0 px-3 py-2 text-xs rounded border border-detec-ui-border text-detec-ink-primary hover:bg-detec-slate-100 transition-colors"
              >
                {keyCopied ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-detec-ink-secondary">
              Key prefix: <span className="font-mono">{rotateResult.prefix}&hellip;</span>
              &ensp;&middot;&ensp;
              Rotated at: {new Date(rotateResult.rotated_at).toLocaleString()}
            </p>
            <button
              onClick={handleDismissResult}
              className="text-xs text-detec-ink-secondary underline hover:text-detec-ink-primary"
            >
              Dismiss
            </button>
          </div>
        )}

        {isOwner && !rotateResult && (
          <button
            className="px-4 py-1.5 text-sm rounded border border-amber-500 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950 transition-colors"
            onClick={() => { setShowRotateConfirm(true); setRotateError(null); }}
          >
            Rotate Agent Key
          </button>
        )}
        {!isOwner && (
          <p className="text-xs text-detec-ink-secondary">Only the organization owner can rotate the agent key.</p>
        )}
      </div>

      {/* Rotate confirmation modal */}
      {showRotateConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-detec-surface border border-detec-ui-border rounded-detec-md shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-base font-semibold text-detec-ink-primary mb-3">Rotate Agent Key?</h3>
            <p className="text-sm text-detec-ink-secondary mb-4">
              This will immediately invalidate all current agent connections. Agents will fail to
              authenticate on their next heartbeat until reconfigured with the new key. This cannot
              be undone.
            </p>
            {rotateError && (
              <p className="text-xs text-red-600 mb-3">{rotateError}</p>
            )}
            <div className="flex gap-2 justify-end">
              <button
                className="px-4 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ink-secondary hover:bg-detec-slate-100 transition-colors"
                onClick={() => { setShowRotateConfirm(false); setRotateError(null); }}
                disabled={rotateLoading}
              >
                Cancel
              </button>
              <button
                className="px-4 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
                onClick={handleRotateKey}
                disabled={rotateLoading}
              >
                {rotateLoading ? 'Rotating\u2026' : 'Rotate Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
