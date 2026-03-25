import { useEffect, useState } from 'react';
import { fetchCurrentTenant, updateTenant } from '../lib/api';

export default function OrgSettingsPage() {
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

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

  if (loading) return <div className="p-8 text-detec-ui-muted">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">{error}</div>;

  const isOwner = tenant.role === 'owner';

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-xl font-semibold text-detec-ui-text mb-6">Organization Settings</h1>
      <div className="bg-detec-surface border border-detec-ui-border rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">Organization name</label>
          {editing ? (
            <input
              id="org-name-input"
              aria-label="Org name"
              className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text focus:outline-none focus:ring-1 focus:ring-detec-ui-accent"
              value={nameInput}
              onChange={e => setNameInput(e.target.value)}
            />
          ) : (
            <p className="text-sm text-detec-ui-text">{tenant.name}</p>
          )}
        </div>
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">Slug</label>
          <p className="text-sm font-mono text-detec-ui-muted">{tenant.slug}</p>
        </div>
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">Subscription tier</label>
          <p className="text-sm text-detec-ui-text capitalize">{tenant.subscription_tier || 'free'}</p>
        </div>
        <div className="flex gap-6 pt-2">
          <div>
            <p className="text-xs text-detec-ui-muted">Members</p>
            <p className="text-lg font-semibold text-detec-ui-text">{tenant.member_count}</p>
          </div>
          <div>
            <p className="text-xs text-detec-ui-muted">Endpoints</p>
            <p className="text-lg font-semibold text-detec-ui-text">{tenant.endpoint_count}</p>
          </div>
        </div>
        {isOwner && !editing && (
          <button
            className="mt-2 px-4 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ui-text hover:bg-detec-slate-100 transition-colors"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        )}
        {editing && (
          <div className="flex gap-2 mt-2">
            <button
              className="px-4 py-1.5 text-sm rounded bg-detec-ui-accent text-white hover:opacity-90 transition-opacity disabled:opacity-50"
              onClick={handleSave}
              disabled={saving || !nameInput.trim()}
            >
              {saving ? 'Saving\u2026' : 'Save'}
            </button>
            <button
              className="px-4 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ui-muted hover:bg-detec-slate-100 transition-colors"
              onClick={() => { setEditing(false); setNameInput(tenant.name); setSaveError(null); }}
            >
              Cancel
            </button>
            {saveError && <p className="text-xs text-red-600 self-center">{saveError}</p>}
          </div>
        )}
      </div>
      {!isOwner && (
        <p className="mt-4 text-xs text-detec-ui-muted">Only the organization owner can edit these settings.</p>
      )}
    </div>
  );
}
