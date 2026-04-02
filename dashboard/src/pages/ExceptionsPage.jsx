import { useState, useEffect, useCallback } from 'react';
import {
  fetchAllowList,
  createAllowListEntry,
  updateAllowListEntry,
  deleteAllowListEntry,
} from '../lib/api';
import ExceptionHistoryDrawer from '../components/dashboard/ExceptionHistoryDrawer';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

function daysUntil(date) {
  if (!date) return null;
  const now = new Date();
  return Math.ceil((date - now) / (1000 * 60 * 60 * 24));
}

function relativeTime(date) {
  if (!date) return null;
  const diff = daysUntil(date);
  if (diff < 0) return `${Math.abs(diff)}d ago`;
  if (diff === 0) return 'today';
  if (diff === 1) return 'in 1 day';
  return `in ${diff} days`;
}

function expiryStatus(entry) {
  if (!entry.expires_at) return 'no-expiry';
  const d = parseDate(entry.expires_at);
  if (!d) return 'no-expiry';
  const diff = daysUntil(d);
  if (diff < 0) return 'expired';
  if (diff <= 7) return 'expiring-soon';
  return 'active';
}

function isExpired(entry) {
  return expiryStatus(entry) === 'expired';
}

const STATUS_LABELS = {
  'no-expiry': { label: 'No expiry', cls: 'bg-red-100 text-red-700 border-red-200' },
  'expired': { label: 'Expired', cls: 'bg-slate-100 text-slate-500 border-slate-200' },
  'expiring-soon': { label: 'Expiring soon', cls: 'bg-amber-100 text-amber-700 border-amber-200' },
  'active': { label: '', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
};

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function ShieldBanIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <line x1="9" y1="9" x2="15" y2="15" />
      <line x1="15" y1="9" x2="9" y2="15" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Input / select helpers matching design system conventions
// ---------------------------------------------------------------------------

const inputCls =
  'w-full bg-white border border-detec-ui-border rounded-detec px-3 py-1.5 text-sm text-detec-ui-text focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent';

// ---------------------------------------------------------------------------
// Drawer (create / edit)
// ---------------------------------------------------------------------------

const EMPTY_FORM = {
  pattern: '',
  pattern_type: 'name',
  owner_id: '',
  reason_code: '',
  scope: 'tenant',
  expires_at: '',
  description: '',
  no_expiry_override: false,
};

function ExceptionDrawer({ entry, onClose, onSaved }) {
  const isEdit = Boolean(entry);

  const [form, setForm] = useState(() => {
    if (!entry) return EMPTY_FORM;
    const expiresLocal = entry.expires_at
      ? new Date(entry.expires_at).toISOString().slice(0, 16)
      : '';
    return {
      pattern: entry.pattern || '',
      pattern_type: entry.pattern_type || 'name',
      owner_id: entry.owner_id || '',
      reason_code: entry.reason_code || '',
      scope: entry.scope || 'tenant',
      expires_at: expiresLocal,
      description: entry.description || '',
      no_expiry_override: !entry.expires_at,
    };
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function validate() {
    if (!form.pattern.trim()) return 'Pattern is required.';
    if (!form.reason_code.trim()) return 'Reason code is required.';
    if (!form.no_expiry_override && !form.expires_at) return 'Expiry date is required unless override is checked.';
    if (form.no_expiry_override && !form.description.trim()) {
      return 'Description is required when creating an exception with no expiry.';
    }
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setError(null);
    setSaving(true);

    const payload = {
      pattern: form.pattern.trim(),
      pattern_type: form.pattern_type,
      owner_id: form.owner_id.trim() || null,
      reason_code: form.reason_code.trim() || null,
      scope: form.scope,
      expires_at: form.no_expiry_override ? null : (form.expires_at ? new Date(form.expires_at).toISOString() : null),
      description: form.description.trim() || null,
    };

    try {
      if (isEdit) {
        await updateAllowListEntry(entry.id, payload);
      } else {
        await createAllowListEntry(payload);
      }
      onSaved();
    } catch (ex) {
      setError(ex.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex" aria-modal="true" role="dialog">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div className="relative ml-auto w-full max-w-md flex flex-col bg-detec-ui-surface border-l border-detec-ui-border shadow-detec-card h-full overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-detec-ui-border sticky top-0 bg-detec-ui-surface z-10">
          <h2 className="text-sm font-semibold text-detec-ui-text">
            {isEdit ? 'Edit Exception' : 'Add Exception'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-detec hover:bg-detec-slate-100 text-detec-ui-muted transition-colors"
            aria-label="Close drawer"
          >
            <XIcon />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-5 py-5 flex-1">
          {error && (
            <div className="rounded-detec border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Pattern */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">
              Pattern <span className="text-red-500">*</span>
            </label>
            <input
              className={inputCls}
              value={form.pattern}
              onChange={(e) => set('pattern', e.target.value)}
              placeholder="e.g. cursor-agent or /usr/local/bin/cursor"
              required
            />
          </div>

          {/* Pattern type */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">
              Pattern type <span className="text-red-500">*</span>
            </label>
            <select
              className={inputCls}
              value={form.pattern_type}
              onChange={(e) => set('pattern_type', e.target.value)}
            >
              <option value="name">name</option>
              <option value="path">path</option>
              <option value="hash">hash</option>
            </select>
          </div>

          {/* Owner */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">
              Owner <span className="text-red-500">*</span>
            </label>
            <input
              className={inputCls}
              value={form.owner_id}
              onChange={(e) => set('owner_id', e.target.value)}
              placeholder="e.g. alice@acme.com or team-security"
            />
          </div>

          {/* Reason code */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">
              Reason code <span className="text-red-500">*</span>
            </label>
            <input
              className={inputCls}
              value={form.reason_code}
              onChange={(e) => set('reason_code', e.target.value)}
              placeholder="e.g. FP-CURSOR-001"
              required
            />
          </div>

          {/* Scope */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">Scope</label>
            <select
              className={inputCls}
              value={form.scope}
              onChange={(e) => set('scope', e.target.value)}
            >
              <option value="tenant">tenant</option>
              <option value="endpoint">endpoint</option>
              <option value="tool">tool</option>
            </select>
          </div>

          {/* Expires at */}
          {!form.no_expiry_override && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-detec-ui-text">
                Expires at <span className="text-red-500">*</span>
              </label>
              <input
                type="datetime-local"
                className={inputCls}
                value={form.expires_at}
                onChange={(e) => set('expires_at', e.target.value)}
                required={!form.no_expiry_override}
              />
            </div>
          )}

          {/* No expiry override */}
          <label className="flex items-start gap-2.5 cursor-pointer select-none">
            <input
              type="checkbox"
              className="mt-0.5 accent-detec-ui-accent"
              checked={form.no_expiry_override}
              onChange={(e) => set('no_expiry_override', e.target.checked)}
            />
            <span className="text-xs text-detec-ui-text leading-snug">
              Override: create exception with no expiry (requires justification)
            </span>
          </label>

          {form.no_expiry_override && (
            <div className="rounded-detec border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800 leading-relaxed">
              Non-expiring exceptions require review at next detection cadence meeting.
            </div>
          )}

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-detec-ui-text">
              Description
              {form.no_expiry_override && <span className="text-red-500"> *</span>}
            </label>
            <textarea
              className={`${inputCls} resize-none`}
              rows={3}
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="Describe why this exception is necessary"
              required={form.no_expiry_override}
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 mt-auto pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-detec border border-detec-ui-border text-sm font-medium text-detec-ui-text hover:bg-detec-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-detec bg-detec-ui-accent text-white text-sm font-medium shadow-detec-sm hover:brightness-110 disabled:opacity-50 transition-all"
            >
              {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Add exception'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation (inline row)
// ---------------------------------------------------------------------------

function DeleteConfirm({ onCancel, onConfirm, busy }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-detec-ui-text font-medium">Delete this exception? This cannot be undone.</span>
      <button
        type="button"
        onClick={onCancel}
        className="px-2 py-1 rounded border border-detec-ui-border text-detec-ui-muted hover:bg-detec-slate-100 transition-colors"
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onConfirm}
        disabled={busy}
        className="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
      >
        {busy ? 'Deleting…' : 'Confirm delete'}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter pill
// ---------------------------------------------------------------------------

function FilterPill({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
        active
          ? 'bg-detec-ui-accent text-white border-detec-ui-accent shadow-detec-sm'
          : 'bg-white border-detec-ui-border text-detec-ui-muted hover:border-detec-slate-300 hover:text-detec-ui-text'
      }`}
    >
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Expiry badge
// ---------------------------------------------------------------------------

function ExpiryBadge({ entry }) {
  const status = expiryStatus(entry);
  const d = parseDate(entry.expires_at);
  const { cls } = STATUS_LABELS[status];

  if (status === 'no-expiry') {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>
        No expiry
      </span>
    );
  }
  if (status === 'expired') {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>
        Expired
      </span>
    );
  }
  if (status === 'expiring-soon') {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>
        Expiring soon · {relativeTime(d)}
      </span>
    );
  }
  // active
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>
      {d.toLocaleDateString()}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const FILTER_OPTIONS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'expiring-soon', label: 'Expiring Soon' },
  { id: 'expired', label: 'Expired' },
];

export default function ExceptionsPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [filter, setFilter] = useState(() => localStorage.getItem('exceptions_filter') || 'all');
  const [search, setSearch] = useState(() => localStorage.getItem('exceptions_search') || '');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editEntry, setEditEntry] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkExtendOpen, setBulkExtendOpen] = useState(false);
  const [newExpiry, setNewExpiry] = useState('');
  const [bulkExtendBusy, setBulkExtendBusy] = useState(false);
  const [historyEntry, setHistoryEntry] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchAllowList();
      // The API only returns non-expired entries; for "Expired" filter we keep
      // what the server sends (which won't include truly expired ones unless the
      // server changes). We still support the UI filter in case future API returns all.
      setEntries(data.items || []);
    } catch (ex) {
      setLoadError(ex.message || 'Failed to load exceptions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    localStorage.setItem('exceptions_filter', filter);
  }, [filter]);

  useEffect(() => {
    localStorage.setItem('exceptions_search', search);
  }, [search]);

  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Escape') {
        setDrawerOpen(false);
        setEditEntry(null);
        setBulkExtendOpen(false);
        setNewExpiry('');
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  function handleOpenCreate() {
    setEditEntry(null);
    setDrawerOpen(true);
  }

  function handleOpenEdit(entry) {
    setEditEntry(entry);
    setDrawerOpen(true);
  }

  function handleCloseDrawer() {
    setDrawerOpen(false);
    setEditEntry(null);
  }

  async function handleSaved() {
    handleCloseDrawer();
    await load();
  }

  async function handleConfirmDelete(id) {
    setDeleteBusy(true);
    try {
      await deleteAllowListEntry(id);
      setDeletingId(null);
      await load();
    } catch (ex) {
      // Show error inline
      alert(ex.message || 'Delete failed.');
    } finally {
      setDeleteBusy(false);
    }
  }

  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function selectAll(items) { setSelectedIds(new Set(items.map(i => i.id))); }
  function clearSelection() { setSelectedIds(new Set()); }

  // Filtering
  const filtered = entries.filter((e) => {
    const status = expiryStatus(e);
    const expired = status === 'expired';
    const active = !expired;

    if (filter === 'active' && !active) return false;
    if (filter === 'expiring-soon' && status !== 'expiring-soon') return false;
    if (filter === 'expired' && !expired) return false;

    if (search) {
      const q = search.toLowerCase();
      if (
        !e.pattern?.toLowerCase().includes(q) &&
        !e.description?.toLowerCase().includes(q) &&
        !e.reason_code?.toLowerCase().includes(q)
      ) {
        return false;
      }
    }

    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-detec bg-detec-ui-accent/10 flex items-center justify-center text-detec-ui-accent">
            <ShieldBanIcon />
          </div>
          <div>
            <h1 className="text-lg font-bold text-detec-ui-text">Exceptions</h1>
            <p className="text-xs text-detec-ui-muted mt-0.5">
              Manage enforcement allow-list entries for this tenant
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleOpenCreate}
          className="flex items-center gap-1.5 px-4 py-2 rounded-detec bg-detec-ui-accent text-white text-sm font-medium shadow-detec-sm hover:brightness-110 transition-all"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Exception
        </button>
      </div>

      {/* Filters + search */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          {FILTER_OPTIONS.map((opt) => (
            <FilterPill
              key={opt.id}
              label={opt.label}
              active={filter === opt.id}
              onClick={() => setFilter(opt.id)}
            />
          ))}
        </div>
        <div className="sm:ml-auto">
          <input
            type="search"
            placeholder="Search pattern or description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${inputCls} w-full sm:w-64`}
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="py-16 flex items-center justify-center text-detec-ui-muted text-sm">
          Loading exceptions…
        </div>
      ) : loadError ? (
        <div className="rounded-detec border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError}
          <button
            type="button"
            onClick={load}
            className="ml-3 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 flex flex-col items-center justify-center gap-2 text-detec-ui-muted">
          <ShieldBanIcon />
          <span className="text-sm">No exceptions found.</span>
          {filter !== 'all' || search ? (
            <button
              type="button"
              onClick={() => { setFilter('all'); setSearch(''); }}
              className="text-xs text-detec-ui-accent hover:underline"
            >
              Clear filters
            </button>
          ) : null}
        </div>
      ) : (
        <>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-3 px-4 py-2 bg-detec-slate-50 border border-detec-ui-border rounded-lg mb-4">
              <span className="text-sm text-detec-ui-muted">{selectedIds.size} selected</span>
              <button className="px-3 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600" onClick={() => setBulkExtendOpen(true)}>Extend expiry</button>
              <button className="text-xs text-detec-ui-muted hover:text-detec-ui-text ml-auto" onClick={clearSelection}>Clear</button>
            </div>
          )}
        <div className="rounded-detec border border-detec-ui-border shadow-detec-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-detec-slate-100 border-b border-detec-ui-border">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide w-8">
                    <input
                      type="checkbox"
                      onChange={e => e.target.checked ? selectAll(filtered) : clearSelection()}
                      checked={selectedIds.size === filtered.length && filtered.length > 0}
                    />
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Pattern
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Type
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Scope
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Owner
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Reason code
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Expires
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Status
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-detec-ui-muted uppercase tracking-wide">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-detec-ui-border">
                {filtered.map((entry) => {
                  const expired = isExpired(entry);
                  const isDeleting = deletingId === entry.id;

                  return (
                    <tr
                      key={entry.id}
                      className={`transition-colors ${expired ? 'opacity-60' : 'hover:bg-detec-slate-100/50'}`}
                    >
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={selectedIds.has(entry.id)} onChange={() => toggleSelect(entry.id)} />
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-detec-ui-text break-all">
                          {entry.pattern}
                        </span>
                        {entry.description && (
                          <p className="text-xs text-detec-ui-muted mt-0.5 max-w-xs truncate">
                            {entry.description}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded bg-detec-slate-100 border border-detec-ui-border text-[11px] font-medium text-detec-ui-muted uppercase">
                          {entry.pattern_type || '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-detec-ui-text">
                        {entry.scope || 'tenant'}
                      </td>
                      <td className="px-4 py-3 text-xs text-detec-ui-text max-w-[120px] truncate">
                        {entry.owner_id || (
                          <span className="text-detec-ui-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {entry.reason_code ? (
                          <span className="font-mono text-xs text-detec-ui-text">
                            {entry.reason_code}
                          </span>
                        ) : (
                          <span className="text-detec-ui-muted text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <ExpiryBadge entry={entry} />
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${
                            expired
                              ? 'bg-slate-100 text-slate-500 border-slate-200'
                              : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          }`}
                        >
                          {expired ? 'Expired' : 'Active'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {isDeleting ? (
                          <DeleteConfirm
                            onCancel={() => setDeletingId(null)}
                            onConfirm={() => handleConfirmDelete(entry.id)}
                            busy={deleteBusy}
                          />
                        ) : (
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleOpenEdit(entry)}
                              title="Edit"
                              className="p-1.5 rounded hover:bg-detec-slate-100 text-detec-ui-muted hover:text-detec-ui-accent transition-colors"
                            >
                              <PencilIcon />
                            </button>
                            <button
                              type="button"
                              onClick={() => setHistoryEntry(entry)}
                              title="View change history"
                              className="p-1.5 rounded hover:bg-detec-slate-100 text-detec-ui-muted hover:text-detec-ui-accent transition-colors"
                            >
                              <ClockIcon />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingId(entry.id)}
                              title="Delete"
                              className="p-1.5 rounded hover:bg-red-50 text-detec-ui-muted hover:text-red-600 transition-colors"
                            >
                              <TrashIcon />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        </>
      )}

      {/* Drawer */}
      {drawerOpen && (
        <ExceptionDrawer
          entry={editEntry}
          onClose={handleCloseDrawer}
          onSaved={handleSaved}
        />
      )}

      {/* History drawer */}
      {historyEntry && (
        <ExceptionHistoryDrawer
          entry={historyEntry}
          onClose={() => setHistoryEntry(null)}
        />
      )}

      {/* Bulk extend expiry modal */}
      {bulkExtendOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-detec-surface border border-detec-ui-border rounded-lg p-6 w-96 space-y-4">
            <h2 className="font-semibold text-detec-ui-text">Extend expiry for {selectedIds.size} entries</h2>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1" htmlFor="new-expiry-input">New expiry</label>
              <input id="new-expiry-input" aria-label="New expiry" type="datetime-local" className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text" value={newExpiry} onChange={e => setNewExpiry(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <button
                className="flex-1 py-1.5 text-sm rounded bg-detec-ui-accent text-white hover:opacity-90 disabled:opacity-50"
                disabled={bulkExtendBusy || !newExpiry}
                onClick={async () => {
                  setBulkExtendBusy(true);
                  try {
                    await Promise.all([...selectedIds].map(id => updateAllowListEntry(id, { expires_at: newExpiry + ':00Z' })));
                    clearSelection();
                    setBulkExtendOpen(false);
                    setNewExpiry('');
                    await load();
                  } catch(e) { alert(e.message); } finally { setBulkExtendBusy(false); }
                }}
              >{bulkExtendBusy ? 'Applying…' : 'Apply'}</button>
              <button className="flex-1 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ui-muted" onClick={() => { setBulkExtendOpen(false); setNewExpiry(''); }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
