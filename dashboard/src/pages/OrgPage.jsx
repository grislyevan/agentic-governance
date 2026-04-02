import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import { fetchMyTenants, createTenant, updateTenant, switchTenant } from '../lib/api';
import { storeTokens } from '../lib/auth';

export default function OrgPage() {
  const { user, refresh } = useAuth();
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [switching, setSwitching] = useState(null);

  const canCreate = user?.role === 'owner' || user?.role === 'admin';

  const loadTenants = useCallback(async () => {
    try {
      const data = await fetchMyTenants();
      setTenants(data);
    } catch {
      setError('Failed to load organizations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTenants(); }, [loadTenants]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError('');
    try {
      await createTenant(newName.trim());
      setNewName('');
      setShowCreate(false);
      await loadTenants();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleUpdate = async (id) => {
    if (!editName.trim()) return;
    setError('');
    try {
      await updateTenant(id, { name: editName.trim() });
      setEditingId(null);
      await loadTenants();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSwitch = async (tenantId) => {
    if (switching || tenantId === user?.tenant_id) return;
    setSwitching(tenantId);
    try {
      const data = await switchTenant(tenantId);
      storeTokens(data);
      await refresh();
      window.location.reload();
    } catch (err) {
      setError(err.message);
      setSwitching(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-detec-brand border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex items-center justify-between">
        <h1 className="text-xl sm:text-2xl font-bold text-detec-ink-primary">Organizations</h1>
        {canCreate && !showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-detec-md bg-detec-brand text-white text-sm font-medium hover:bg-detec-brand transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
            New Organization
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="rounded-detec-md border border-detec-brand/30 bg-detec-surface/80 p-5 space-y-4 max-w-lg">
          <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">Create Organization</h2>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Name</span>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Acme Corp"
              autoFocus
              className="w-full bg-detec-void border border-detec-ui-border rounded-detec-md px-3 py-2 text-sm text-detec-ink-primary placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/50 transition-colors"
            />
          </label>
          <p className="text-xs text-detec-ink-secondary">
            You will become the owner of the new organization. Your existing account stays intact.
          </p>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={creating || !newName.trim()}
              className="px-4 py-2 rounded-detec-md bg-detec-brand text-white text-sm font-medium hover:bg-detec-brand disabled:opacity-50 transition-colors"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => { setShowCreate(false); setNewName(''); }}
              className="px-4 py-2 rounded-detec-md border border-detec-ui-border text-detec-ink-secondary text-sm hover:text-detec-ink-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tenants.map((t) => {
          const isCurrent = t.id === user?.tenant_id;
          return (
            <div
              key={t.id}
              className={`rounded-detec-md border p-5 space-y-3 transition-colors ${
                isCurrent
                  ? 'border-detec-brand/40 bg-detec-brand/5'
                  : 'border-detec-ui-border/50 bg-detec-surface/80 hover:border-detec-ui-border'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <span className={`w-8 h-8 rounded-detec-md flex items-center justify-center text-sm font-bold ${
                    isCurrent
                      ? 'bg-detec-brand-muted text-detec-brand'
                      : 'bg-detec-slate-200 text-detec-ink-primary'
                  }`}>
                    {t.name[0].toUpperCase()}
                  </span>
                  <div>
                    {editingId === t.id ? (
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onBlur={() => handleUpdate(t.id)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleUpdate(t.id); if (e.key === 'Escape') setEditingId(null); }}
                        autoFocus
                        className="bg-detec-void border border-detec-brand/50 rounded px-2 py-0.5 text-sm text-detec-ink-primary focus:outline-none w-36"
                      />
                    ) : (
                      <h3 className="text-sm font-semibold text-detec-ink-primary">{t.name}</h3>
                    )}
                    <p className="text-[11px] text-detec-ink-secondary">{t.slug}</p>
                  </div>
                </div>
                {isCurrent && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-detec-brand-muted text-detec-brand">
                    Current
                  </span>
                )}
              </div>

              <div className="flex gap-4 text-xs text-detec-ink-secondary">
                <span>{t.member_count} member{t.member_count !== 1 ? 's' : ''}</span>
                <span>{t.endpoint_count} endpoint{t.endpoint_count !== 1 ? 's' : ''}</span>
                <span className="capitalize">{t.subscription_tier}</span>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-detec-ink-secondary capitalize">{t.role}</span>
                <div className="flex-1" />
                {t.role === 'owner' && editingId !== t.id && (
                  <button
                    onClick={() => { setEditingId(t.id); setEditName(t.name); }}
                    className="text-xs text-detec-ink-secondary hover:text-detec-ink-primary transition-colors"
                    title="Rename"
                  >
                    Rename
                  </button>
                )}
                {!isCurrent && (
                  <button
                    onClick={() => handleSwitch(t.id)}
                    disabled={switching === t.id}
                    className="px-3 py-1 rounded-md bg-detec-brand/10 text-detec-brand text-xs font-medium hover:bg-detec-brandHover/20 disabled:opacity-50 transition-colors"
                  >
                    {switching === t.id ? 'Switching...' : 'Switch'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {tenants.length === 0 && (
        <div className="text-center py-12 text-detec-ink-secondary text-sm">
          No organizations found. Create one to get started.
        </div>
      )}
    </div>
  );
}
