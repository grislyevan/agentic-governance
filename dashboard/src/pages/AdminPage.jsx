import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import { fetchUsers, createUser, updateUser, deleteUser } from '../lib/api';

const ROLE_BADGES = {
  owner:   'bg-amber-900/40 text-amber-400 border-amber-700/40',
  admin:   'bg-blue-900/40 text-blue-400 border-blue-700/40',
  analyst: 'bg-teal-900/40 text-teal-400 border-teal-700/40',
  viewer:  'bg-slate-800/60 text-slate-400 border-slate-700/40',
};

const ASSIGNABLE_ROLES = ['admin', 'analyst', 'viewer'];

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  const canManage = currentUser?.role === 'owner' || currentUser?.role === 'admin';

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUsers({ page, perPage: 50, search: search || undefined });
      setUsers(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  if (!canManage) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-detec-slate-100">Admin</h1>
        <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
          <div className="text-detec-slate-400 text-sm font-medium mb-1">Access restricted</div>
          <div className="text-detec-slate-600 text-sm">You need an admin or owner role to manage users.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-detec-slate-100">Users</h1>
        <button
          onClick={() => { setEditingUser(null); setShowForm(true); }}
          className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 transition-colors"
        >
          Add user
        </button>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-72 rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 placeholder-detec-slate-500 focus:border-detec-primary-500 focus:outline-none"
        />
        <span className="text-xs text-detec-slate-500">{total} user{total !== 1 ? 's' : ''}</span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      <div className="rounded-xl border border-detec-slate-700/60 bg-detec-slate-800/50 overflow-hidden">
        <table className="w-full text-sm" aria-label="Users">
          <thead>
            <tr className="border-b border-detec-slate-700/40 text-left text-xs font-medium uppercase tracking-wider text-detec-slate-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Provider</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-detec-slate-500 text-sm">Loading...</td>
              </tr>
            )}
            {!loading && users.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-detec-slate-500 text-sm">No users found.</td>
              </tr>
            )}
            {!loading && users.map((u) => (
              <UserRow
                key={u.id}
                u={u}
                currentUser={currentUser}
                onEdit={() => { setEditingUser(u); setShowForm(true); }}
                onToggleActive={async () => {
                  try {
                    if (u.is_active) {
                      if (currentUser.role === 'owner') {
                        await deleteUser(u.id);
                      } else {
                        await updateUser(u.id, { is_active: false });
                      }
                    } else {
                      await updateUser(u.id, { is_active: true });
                    }
                    loadUsers();
                  } catch (err) { setError(err.message); }
                }}
              />
            ))}
          </tbody>
        </table>
      </div>

      {total > 50 && (
        <div className="flex items-center justify-between pt-1">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="rounded-lg border border-detec-slate-700 px-3 py-1.5 text-xs text-detec-slate-400 hover:bg-detec-slate-800 disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-xs text-detec-slate-500">
            Page {page} of {Math.ceil(total / 50)}
          </span>
          <button
            disabled={page * 50 >= total}
            onClick={() => setPage(p => p + 1)}
            className="rounded-lg border border-detec-slate-700 px-3 py-1.5 text-xs text-detec-slate-400 hover:bg-detec-slate-800 disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}

      {showForm && (
        <UserFormModal
          user={editingUser}
          currentUser={currentUser}
          onClose={() => { setShowForm(false); setEditingUser(null); }}
          onSaved={() => { setShowForm(false); setEditingUser(null); loadUsers(); }}
          onError={setError}
        />
      )}
    </div>
  );
}


function UserRow({ u, currentUser, onEdit, onToggleActive }) {
  const displayName = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email;
  const initials = [u.first_name?.[0], u.last_name?.[0]].filter(Boolean).join('').toUpperCase() || u.email[0].toUpperCase();
  const isOwner = u.role === 'owner';
  const isSelf = u.id === currentUser?.id;

  return (
    <tr className="border-b border-detec-slate-700/20 hover:bg-detec-slate-800/40 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-detec-slate-700 text-xs font-semibold text-detec-slate-300">
            {initials}
          </div>
          <span className="font-medium text-detec-slate-200">{displayName}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-detec-slate-400">{u.email}</td>
      <td className="px-4 py-3">
        <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-medium ${ROLE_BADGES[u.role] || ROLE_BADGES.viewer}`}>
          {u.role}
        </span>
      </td>
      <td className="px-4 py-3 text-detec-slate-500 text-xs">{u.auth_provider}</td>
      <td className="px-4 py-3">
        {u.is_active ? (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-detec-slate-500">
            <span className="h-1.5 w-1.5 rounded-full bg-detec-slate-600" />Inactive
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-detec-slate-500 text-xs">
        {new Date(u.created_at).toLocaleDateString()}
      </td>
      <td className="px-4 py-3 text-right">
        {!isOwner && !isSelf && (
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={onEdit}
              className="rounded px-2 py-1 text-xs text-detec-slate-400 hover:bg-detec-slate-700 hover:text-detec-slate-200 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={onToggleActive}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                u.is_active
                  ? 'text-red-400 hover:bg-red-950/40'
                  : 'text-emerald-400 hover:bg-emerald-950/40'
              }`}
            >
              {u.is_active ? 'Deactivate' : 'Reactivate'}
            </button>
          </div>
        )}
        {isSelf && <span className="text-xs text-detec-slate-600">You</span>}
        {isOwner && !isSelf && <span className="text-xs text-detec-slate-600">Owner</span>}
      </td>
    </tr>
  );
}


function UserFormModal({ user, currentUser, onClose, onSaved, onError }) {
  const isEdit = !!user;
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [role, setRole] = useState(user?.role || 'analyst');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      if (isEdit) {
        const patch = {};
        if (firstName !== (user.first_name || '')) patch.first_name = firstName;
        if (lastName !== (user.last_name || '')) patch.last_name = lastName || null;
        if (role !== user.role) patch.role = role;
        if (Object.keys(patch).length === 0) { onSaved(); return; }
        await updateUser(user.id, patch);
      } else {
        if (!firstName.trim()) { setFormError('First name is required'); setSubmitting(false); return; }
        if (!email.trim()) { setFormError('Email is required'); setSubmitting(false); return; }
        if (password.length < 8) { setFormError('Password must be at least 8 characters'); setSubmitting(false); return; }
        await createUser({
          first_name: firstName.trim(),
          last_name: lastName.trim() || null,
          email: email.trim(),
          role,
          password,
        });
      }
      onSaved();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">
          {isEdit ? 'Edit User' : 'Add User'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">First name</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
                required={!isEdit}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Last name</label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
              />
            </div>
          </div>

          {!isEdit && (
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
            >
              {ASSIGNABLE_ROLES.map((r) => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          </div>

          {!isEdit && (
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Temporary password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
                required
                minLength={8}
                placeholder="Min. 8 characters"
              />
              <p className="mt-1 text-xs text-detec-slate-600">
                Share this password securely. The user should change it on first login.
              </p>
            </div>
          )}

          {formError && (
            <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 disabled:opacity-50"
            >
              {submitting ? 'Saving...' : isEdit ? 'Save changes' : 'Create user'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
