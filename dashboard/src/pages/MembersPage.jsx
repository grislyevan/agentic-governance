import { useEffect, useState } from 'react';
import { fetchUsers, createUser, updateUser, deactivateUser } from '../lib/api';

const ROLES = ['owner', 'admin', 'analyst', 'viewer'];

export default function MembersPage() {
  const [members, setMembers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('analyst');
  const [addError, setAddError] = useState(null);
  const [addBusy, setAddBusy] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(null);

  function load() {
    setLoading(true);
    fetchUsers()
      .then(d => { setMembers(d.items); setTotal(d.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  const ownerCount = members.filter(m => m.role === 'owner' && m.is_active).length;

  async function handleAdd() {
    setAddBusy(true);
    setAddError(null);
    try {
      await createUser({ email: newEmail, password: newPassword, role: newRole });
      setAddOpen(false);
      setNewEmail(''); setNewPassword(''); setNewRole('analyst');
      load();
    } catch (e) {
      setAddError(e.message);
    } finally {
      setAddBusy(false);
    }
  }

  async function handleRoleChange(userId, role) {
    try {
      await updateUser(userId, { role });
      load();
    } catch (e) {
      alert(e.message);
    }
  }

  async function handleDeactivate(userId) {
    try {
      await deactivateUser(userId);
      setConfirmDeactivate(null);
      load();
    } catch (e) {
      alert(e.message);
    }
  }

  if (loading) return <div className="p-8 text-detec-ui-muted">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">{error}</div>;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-detec-ui-text">Members ({total})</h1>
        <button
          className="px-4 py-1.5 text-sm rounded bg-detec-ui-accent text-white hover:opacity-90"
          onClick={() => setAddOpen(true)}
        >
          Add member
        </button>
      </div>

      <div className="bg-detec-surface border border-detec-ui-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-detec-ui-border bg-detec-slate-50">
              <th className="px-4 py-2 text-left text-xs font-medium text-detec-ui-muted">Email</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-detec-ui-muted">Name</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-detec-ui-muted">Role</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-detec-ui-muted">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-detec-ui-muted">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map(m => {
              const isLastOwner = m.role === 'owner' && ownerCount === 1;
              return (
                <tr key={m.id} className="border-b border-detec-ui-border last:border-0">
                  <td className="px-4 py-3 text-detec-ui-text">{m.email}</td>
                  <td className="px-4 py-3 text-detec-ui-muted">
                    {[m.first_name, m.last_name].filter(Boolean).join(' ') || '\u2014'}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className="text-xs border border-detec-ui-border rounded px-2 py-0.5 bg-detec-bg text-detec-ui-text"
                      value={m.role}
                      disabled={isLastOwner}
                      onChange={e => handleRoleChange(m.id, e.target.value)}
                    >
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${
                      m.is_active
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-500 border-slate-200'
                    }`}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {!isLastOwner && m.is_active && (
                      confirmDeactivate === m.id ? (
                        <div className="flex items-center gap-2">
                          <button
                            className="text-xs text-white bg-red-500 hover:bg-red-600 px-2 py-0.5 rounded"
                            onClick={() => handleDeactivate(m.id)}
                          >
                            Confirm
                          </button>
                          <button
                            className="text-xs text-detec-ui-muted hover:text-detec-ui-text"
                            onClick={() => setConfirmDeactivate(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          className="text-xs text-detec-ui-muted hover:text-red-600"
                          onClick={() => setConfirmDeactivate(m.id)}
                        >
                          Deactivate
                        </button>
                      )
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {addOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-detec-surface border border-detec-ui-border rounded-lg p-6 w-96 space-y-4">
            <h2 className="font-semibold text-detec-ui-text">Add member</h2>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Email</label>
              <input type="email" className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text" value={newEmail} onChange={e => setNewEmail(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Password</label>
              <input type="password" className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Role</label>
              <select className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text" value={newRole} onChange={e => setNewRole(e.target.value)}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            {addError && <p className="text-xs text-red-600">{addError}</p>}
            <div className="flex gap-2">
              <button className="flex-1 py-1.5 text-sm rounded bg-detec-ui-accent text-white hover:opacity-90 disabled:opacity-50" disabled={addBusy || !newEmail || !newPassword} onClick={handleAdd}>
                {addBusy ? 'Adding\u2026' : 'Add'}
              </button>
              <button className="flex-1 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ui-muted hover:bg-detec-slate-100" onClick={() => { setAddOpen(false); setAddError(null); }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
