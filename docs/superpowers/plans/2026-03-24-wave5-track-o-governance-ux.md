# Wave 5 Track O — Tenant/Admin Governance UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the admin governance UX — org settings page, membership management, tenant-scoped dashboard consistency, admin-only panels, and bulk governance actions.

**Architecture:** All major backend endpoints already exist (`/tenants`, `/users`, `/approvals`, `/enforcement/allow-list`). This track is primarily frontend work: new pages (OrgSettings, Members), RBAC-gated panel visibility, global tenant context consistency, and bulk actions in ApprovalsPage/ExceptionsPage. One backend gap: no user invite-by-email flow; we create users directly (consistent with existing `POST /users`) and add a `deactivate` path via `PATCH /users/:id`.

**Tech Stack:** React + Vitest (dashboard), existing FastAPI endpoints (backend). No new API routes unless stated explicitly.

---

## Existing API endpoints available

| Route | What it does |
|-------|-------------|
| `GET /tenants/current` | Tenant name, slug, subscription_tier, member_count, endpoint_count, role |
| `PATCH /tenants/:id` | Update tenant name (owner only) |
| `GET /users` | List users in tenant (owner/admin), supports search |
| `POST /users` | Create user with email+password, assigns to caller's tenant |
| `PATCH /users/:id` | Update user (role, first_name, last_name) — check existing schema |
| `GET /approvals?status=pending` | Pending approval queue |
| `POST /approvals/:id/approve` | Approve with reason |
| `POST /approvals/:id/deny` | Deny with reason |
| `GET /enforcement/allow-list` | Allow-list entries |
| `PATCH /enforcement/allow-list/:id` | Update allow-list entry (Track M) |

---

## File Map

### New files
- `dashboard/src/pages/OrgSettingsPage.jsx` — Tenant metadata view/edit with re-auth gate
- `dashboard/src/pages/MembersPage.jsx` — Member list, add member, role change, deactivate
- `dashboard/src/tests/OrgSettingsPage.test.jsx` — Vitest tests
- `dashboard/src/tests/MembersPage.test.jsx` — Vitest tests

### Modified files
- `dashboard/src/App.jsx` — Add routes for `/org-settings` and `/members`
- `dashboard/src/lib/api.js` — Add `fetchCurrentTenant`, `updateTenant`, `deactivateUser` functions
- `dashboard/src/pages/DashboardPage.jsx` — RBAC-gate admin panels; verify tenant context
- `dashboard/src/pages/ApprovalsPage.jsx` — Add bulk approve/deny with reason templates
- `dashboard/src/pages/ExceptionsPage.jsx` — Add bulk expiry extension
- Dashboard `Sidebar.jsx` or nav component — Add links to new pages

---

## Task 1: O1.1 — Organization settings page

**Files:**
- Create: `dashboard/src/pages/OrgSettingsPage.jsx`
- Modify: `dashboard/src/lib/api.js`
- Modify: `dashboard/src/App.jsx`
- Modify: dashboard Sidebar/nav

- [ ] **Step 1.1: Add API functions in api.js**

In `dashboard/src/lib/api.js`, add:

```javascript
export async function fetchCurrentTenant() {
  return apiFetch('/tenants/current');
}

export async function updateTenant(tenantId, data) {
  return apiMutate('PATCH', `/tenants/${tenantId}`, data);
}
```

- [ ] **Step 1.2: Write failing tests**

```jsx
// dashboard/src/tests/OrgSettingsPage.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import OrgSettingsPage from '../pages/OrgSettingsPage';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth', () => ({
  getStoredTokens: () => ({ accessToken: 'fake' }),
  getUserRole: () => 'owner',
}));

describe('OrgSettingsPage', () => {
  it('displays tenant details', async () => {
    api.fetchCurrentTenant.mockResolvedValue({
      id: 't1', name: 'Acme', slug: 'acme',
      subscription_tier: 'pro', member_count: 3, endpoint_count: 5, role: 'owner',
    });
    render(<OrgSettingsPage />);
    await waitFor(() => expect(screen.getByText('Acme')).toBeInTheDocument());
    expect(screen.getByText('3')).toBeInTheDocument(); // member count
  });

  it('shows edit form only for owner', async () => {
    api.fetchCurrentTenant.mockResolvedValue({
      id: 't1', name: 'Acme', slug: 'acme',
      subscription_tier: 'pro', member_count: 3, endpoint_count: 5, role: 'analyst',
    });
    render(<OrgSettingsPage />);
    await waitFor(() => screen.getByText('Acme'));
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
  });

  it('calls updateTenant on save', async () => {
    api.fetchCurrentTenant.mockResolvedValue({
      id: 't1', name: 'Acme', slug: 'acme',
      subscription_tier: 'pro', member_count: 3, endpoint_count: 5, role: 'owner',
    });
    api.updateTenant.mockResolvedValue({ id: 't1', name: 'Acme Corp', slug: 'acme-corp' });
    render(<OrgSettingsPage />);
    await waitFor(() => screen.getByText('Acme'));
    await userEvent.click(screen.getByRole('button', { name: /edit/i }));
    await userEvent.clear(screen.getByLabelText(/org name/i));
    await userEvent.type(screen.getByLabelText(/org name/i), 'Acme Corp');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(api.updateTenant).toHaveBeenCalledWith('t1', { name: 'Acme Corp' });
  });
});
```

Run to confirm failure:
```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- OrgSettingsPage 2>&1 | tail -10
```

- [ ] **Step 1.3: Implement OrgSettingsPage.jsx**

```jsx
// dashboard/src/pages/OrgSettingsPage.jsx
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
        {/* Name field */}
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">
            Organization name
          </label>
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

        {/* Slug */}
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">Slug</label>
          <p className="text-sm font-mono text-detec-ui-muted">{tenant.slug}</p>
        </div>

        {/* Tier */}
        <div>
          <label className="block text-xs font-medium text-detec-ui-muted mb-1">
            Subscription tier
          </label>
          <p className="text-sm text-detec-ui-text capitalize">{tenant.subscription_tier || 'free'}</p>
        </div>

        {/* Stats */}
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

        {/* Actions */}
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
              {saving ? 'Saving…' : 'Save'}
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
        <p className="mt-4 text-xs text-detec-ui-muted">
          Only the organization owner can edit these settings.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 1.4: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- OrgSettingsPage 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 1.5: Add route and nav link**

In `dashboard/src/App.jsx`, add:
```jsx
import OrgSettingsPage from './pages/OrgSettingsPage';
// ...in routes:
<Route path="/org-settings" element={<OrgSettingsPage />} />
```

In the Sidebar/nav component, add a link "Org Settings" under the admin section, visible only to owner/admin roles.

- [ ] **Step 1.6: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/OrgSettingsPage.jsx \
  dashboard/src/tests/OrgSettingsPage.test.jsx \
  dashboard/src/App.jsx \
  dashboard/src/lib/api.js
git commit -m "feat(dashboard): add OrgSettingsPage with RBAC-gated edit (O1.1)"
```

---

## Task 2: O1.2 — Members management page

**Files:**
- Create: `dashboard/src/pages/MembersPage.jsx`
- Create: `dashboard/src/tests/MembersPage.test.jsx`
- Modify: `dashboard/src/lib/api.js` (add deactivateUser)
- Modify: `dashboard/src/App.jsx` (add route)

### Backend note
`PATCH /users/:id` handles role changes. "Deactivate" = PATCH with `is_active: false`. Verify the `UserUpdate` schema in `api/schemas/users.py` includes `is_active`. If not, add it (this is a minor backend addition and part of this task).

### Role matrix enforcement (frontend)
- Cannot remove last owner: check `member_count === 1 && user.role === 'owner'` before allowing deactivate/role-downgrade.
- Cannot escalate viewer → owner without confirmation.

- [ ] **Step 2.1: Check UserUpdate schema**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
grep -n "is_active\|UserUpdate" api/schemas/users.py
```

If `is_active` is not in `UserUpdate`, add it:

```python
# in api/schemas/users.py, find UserUpdate
class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    is_active: bool | None = None  # add this
```

If the `User` model doesn't have `is_active`, check `api/models/user.py`. Add the column if missing and create a migration.

- [ ] **Step 2.2: Add deactivateUser to api.js**

```javascript
export async function deactivateUser(id) {
  return apiMutate('PATCH', `/users/${id}`, { is_active: false });
}
```

- [ ] **Step 2.3: Write failing tests**

```jsx
// dashboard/src/tests/MembersPage.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import MembersPage from '../pages/MembersPage';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth', () => ({
  getStoredTokens: () => ({ accessToken: 'fake' }),
  getUserRole: () => 'owner',
  getCurrentUserId: () => 'u-owner',
}));

const mockUsers = {
  items: [
    { id: 'u-owner', email: 'owner@co.com', role: 'owner', first_name: 'Alice', last_name: 'O', is_active: true },
    { id: 'u-admin', email: 'admin@co.com', role: 'admin', first_name: 'Bob', last_name: 'A', is_active: true },
  ],
  total: 2,
  page: 1,
  per_page: 50,
};

describe('MembersPage', () => {
  it('renders member list', async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    render(<MembersPage />);
    await waitFor(() => expect(screen.getByText('owner@co.com')).toBeInTheDocument());
    expect(screen.getByText('admin@co.com')).toBeInTheDocument();
  });

  it('cannot deactivate the last owner', async () => {
    api.fetchUsers.mockResolvedValue({
      ...mockUsers,
      items: [mockUsers.items[0]], // only one user, who is owner
      total: 1,
    });
    render(<MembersPage />);
    await waitFor(() => screen.getByText('owner@co.com'));
    const deactivateButtons = screen.queryAllByRole('button', { name: /deactivate/i });
    expect(deactivateButtons).toHaveLength(0);
  });

  it('calls deactivateUser on confirm', async () => {
    api.fetchUsers.mockResolvedValue(mockUsers);
    api.deactivateUser.mockResolvedValue({ id: 'u-admin', is_active: false });
    render(<MembersPage />);
    await waitFor(() => screen.getByText('admin@co.com'));
    const deactivateBtn = screen.getAllByRole('button', { name: /deactivate/i })[0];
    await userEvent.click(deactivateBtn);
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    expect(api.deactivateUser).toHaveBeenCalledWith('u-admin');
  });
});
```

Run to confirm failure:
```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- MembersPage 2>&1 | tail -10
```

- [ ] **Step 2.4: Implement MembersPage.jsx**

Key behaviors to implement:
- Fetch users with `fetchUsers()`; display in a table: name, email, role badge, status badge, actions
- "Add member" button → modal with email + role selector → calls `createUser`
- Role badge dropdown (owner/admin/analyst/viewer) → calls `updateUser(id, { role })`
- "Deactivate" button → confirmation modal → calls `deactivateUser(id)`
- Guard: if only 1 owner and this user is that owner → hide deactivate and disable role-downgrade
- Guard: cross-tenant ops are denied by API (RBAC) — frontend need not duplicate, but show friendly error on 403

The structure closely mirrors `ExceptionsPage.jsx` — follow the same table + drawer pattern.

Minimum implementation:

```jsx
// dashboard/src/pages/MembersPage.jsx
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
  const [confirmDeactivate, setConfirmDeactivate] = useState(null); // userId

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
                    {[m.first_name, m.last_name].filter(Boolean).join(' ') || '—'}
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

      {/* Add member modal */}
      {addOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-detec-surface border border-detec-ui-border rounded-lg p-6 w-96 space-y-4">
            <h2 className="font-semibold text-detec-ui-text">Add member</h2>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Email</label>
              <input
                type="email"
                className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Password</label>
              <input
                type="password"
                className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Role</label>
              <select
                className="w-full border border-detec-ui-border rounded px-3 py-1.5 text-sm bg-detec-bg text-detec-ui-text"
                value={newRole}
                onChange={e => setNewRole(e.target.value)}
              >
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            {addError && <p className="text-xs text-red-600">{addError}</p>}
            <div className="flex gap-2">
              <button
                className="flex-1 py-1.5 text-sm rounded bg-detec-ui-accent text-white hover:opacity-90 disabled:opacity-50"
                disabled={addBusy || !newEmail || !newPassword}
                onClick={handleAdd}
              >
                {addBusy ? 'Adding…' : 'Add'}
              </button>
              <button
                className="flex-1 py-1.5 text-sm rounded border border-detec-ui-border text-detec-ui-muted hover:bg-detec-slate-100"
                onClick={() => { setAddOpen(false); setAddError(null); }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2.5: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- MembersPage 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 2.6: Add route and nav link**

In `App.jsx`:
```jsx
import MembersPage from './pages/MembersPage';
// in routes:
<Route path="/members" element={<MembersPage />} />
```

Add "Members" link to Sidebar, visible only to owner/admin.

- [ ] **Step 2.7: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/MembersPage.jsx \
  dashboard/src/tests/MembersPage.test.jsx \
  dashboard/src/App.jsx \
  dashboard/src/lib/api.js
git commit -m "feat(dashboard): add MembersPage with invite/role/deactivate (O1.2)"
```

---

## Task 3: O2 — Tenant context consistency

**Files:**
- Modify: `dashboard/src/pages/DashboardPage.jsx` (and other pages if needed)

The `useTenants` hook and `getActiveTenantId` were added in Wave 4 (J1). This task verifies no stale-data bleed after tenant switch and ensures breadcrumb/header shows active tenant.

- [ ] **Step 3.1: Audit current tenant usage**

Search for `getActiveTenantId` usage:
```bash
grep -rn "getActiveTenantId\|activeTenantId\|activeTenant" \
  /Users/echance/Documents/Cursor/agentic-governance/dashboard/src --include="*.jsx" --include="*.js"
```

For each page that makes API calls, verify the call includes the active tenant context (most API calls are scoped server-side by the JWT, so no explicit tenant_id param is usually needed — but verify the TopBar shows the active tenant name).

- [ ] **Step 3.2: Verify tenant switch flushes page data**

The existing tenant switch calls `window.location.reload()` (from Wave 4 J1). This is sufficient for stale-data prevention. Verify this is still in place:

```bash
grep -n "location.reload" \
  /Users/echance/Documents/Cursor/agentic-governance/dashboard/src/lib/auth.js
```

If it's missing, add the reload after a successful tenant switch.

- [ ] **Step 3.3: Check TopBar shows active tenant + role**

In the TopBar/Header component, verify it displays both the active tenant name AND the current user's role context. If the role is not shown, add a role badge (e.g., `<span>owner</span>`) next to the tenant name.

- [ ] **Step 3.4: Write failing tests for admin panel gating**

```jsx
// Add to existing dashboard tests or create dashboard/src/tests/DashboardPage.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import DashboardPage from '../pages/DashboardPage';
import * as auth from '../lib/auth';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth');

describe('DashboardPage role gating', () => {
  it('shows admin-only panels for owner', async () => {
    auth.getUserRole.mockReturnValue('owner');
    api.fetchEndpoints.mockResolvedValue({ items: [], total: 0 });
    // mock other required api calls
    render(<DashboardPage />);
    await waitFor(() => {
      // PostureSummaryWidget and CapabilityDriftWidget should be present
      expect(screen.getByTestId('posture-summary-widget')).toBeInTheDocument();
    });
  });

  it('hides admin-only panels for viewer', async () => {
    auth.getUserRole.mockReturnValue('viewer');
    api.fetchEndpoints.mockResolvedValue({ items: [], total: 0 });
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.queryByTestId('posture-summary-widget')).not.toBeInTheDocument();
    });
  });

  it('shows 403 fallback UI when analyst hits admin endpoint', async () => {
    auth.getUserRole.mockReturnValue('analyst');
    api.fetchEndpoints.mockRejectedValue(new Error('Authentication failed. Check your credentials.'));
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    });
  });
});
```

Run to confirm failure:
```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- DashboardPage 2>&1 | tail -10
```

- [ ] **Step 3.5: Implement admin-only dashboard panels**

In `DashboardPage.jsx`, add role check and gating. Add `data-testid` attributes to gated widgets so tests can target them:

```jsx
import { getUserRole } from '../lib/auth';
// ...
const role = getUserRole();
const isAdminOrOwner = ['owner', 'admin'].includes(role);

// In render — add data-testid to the widget wrapper:
{isAdminOrOwner && (
  <div data-testid="posture-summary-widget">
    <PostureSummaryWidget ... />
  </div>
)}
{isAdminOrOwner && <CapabilityDriftWidget ... />}
```

For 403 fallback: wrap the page's main data-loading effect in a try/catch that sets an `accessDenied` state. Render `<p>Access denied</p>` (or similar) when set.

- [ ] **Step 3.6: Run dashboard tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- DashboardPage 2>&1 | tail -20
```

Expected: All pass including new role-gating tests.

- [ ] **Step 3.7: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/DashboardPage.jsx \
  dashboard/src/tests/DashboardPage.test.jsx
git commit -m "feat(dashboard): gate admin panels by role, verify tenant context (O2)"
```

---

## Task 4: O3.1 — Bulk approve/deny in ApprovalsPage

**Files:**
- Modify: `dashboard/src/pages/ApprovalsPage.jsx`

- [ ] **Step 4.1: Add selection state to pending tab**

Add a `Set` of selected approval IDs:
```jsx
const [selectedIds, setSelectedIds] = useState(new Set());

function toggleSelect(id) {
  setSelectedIds(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
}

function selectAll(items) {
  setSelectedIds(new Set(items.map(i => i.id)));
}

function clearSelection() {
  setSelectedIds(new Set());
}
```

Add a checkbox column to the pending table. Add "Select all" checkbox in the table header.

- [ ] **Step 4.2: Add bulk action bar (appears when items selected)**

```jsx
{selectedIds.size > 0 && (
  <div className="flex items-center gap-3 px-4 py-2 bg-detec-slate-50 border border-detec-ui-border rounded-lg mb-4">
    <span className="text-sm text-detec-ui-muted">{selectedIds.size} selected</span>
    <button
      className="px-3 py-1 text-xs rounded bg-emerald-500 text-white hover:bg-emerald-600"
      onClick={() => openBulkDecision('approve')}
    >
      Approve all
    </button>
    <button
      className="px-3 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600"
      onClick={() => openBulkDecision('deny')}
    >
      Deny all
    </button>
    <button
      className="text-xs text-detec-ui-muted hover:text-detec-ui-text ml-auto"
      onClick={clearSelection}
    >
      Clear selection
    </button>
  </div>
)}
```

- [ ] **Step 4.3: Add bulk decision modal with reason templates**

```jsx
// Reason templates
const REASON_TEMPLATES = {
  approve: ['Approved by security review', 'Expected behavior for this tool', 'Temporary allow for maintenance'],
  deny: ['Violates security policy', 'Unauthorized tool usage', 'Exceeds approved scope'],
};

const [bulkDecision, setBulkDecision] = useState(null); // 'approve' | 'deny' | null
const [bulkReason, setBulkReason] = useState('');
const [bulkBusy, setBulkBusy] = useState(false);

async function executeBulkDecision() {
  setBulkBusy(true);
  const action = bulkDecision === 'approve' ? approveRequest : denyRequest;
  const ids = [...selectedIds];
  try {
    await Promise.all(ids.map(id => action(id, bulkReason)));
    clearSelection();
    setBulkDecision(null);
    setBulkReason('');
    // Refresh the list
    loadApprovals();
  } catch (e) {
    alert(`Some actions failed: ${e.message}`);
  } finally {
    setBulkBusy(false);
  }
}
```

Include template picker:
```jsx
<div className="flex flex-wrap gap-1 mb-2">
  {(REASON_TEMPLATES[bulkDecision] || []).map(t => (
    <button
      key={t}
      className="text-xs px-2 py-0.5 rounded border border-detec-ui-border hover:bg-detec-slate-100"
      onClick={() => setBulkReason(t)}
    >
      {t}
    </button>
  ))}
</div>
```

- [ ] **Step 4.4: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- ApprovalsPage 2>&1 | tail -20
```

Add or update tests to cover:
- Checkboxes appear on pending tab
- Bulk bar appears only when items selected
- Bulk approve calls approveRequest for each selected ID

- [ ] **Step 4.5: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/ApprovalsPage.jsx
git commit -m "feat(dashboard): bulk approve/deny with reason templates (O3.1)"
```

---

## Task 5: O3.1 — Bulk expiry extension in ExceptionsPage

**Files:**
- Modify: `dashboard/src/pages/ExceptionsPage.jsx`

- [ ] **Step 5.1: Write failing tests for bulk expiry extension**

```jsx
// Add to dashboard/src/tests/ExceptionsPage.test.jsx
describe('ExceptionsPage bulk expiry extension', () => {
  it('shows bulk action bar when entries are selected', async () => {
    api.fetchAllowList.mockResolvedValue({ items: [
      { id: 'e1', pattern: 'cursor.exe', pattern_type: 'process_name',
        expires_at: new Date(Date.now() + 86400000).toISOString(), is_active: true },
      { id: 'e2', pattern: 'code.exe', pattern_type: 'process_name',
        expires_at: new Date(Date.now() + 86400000).toISOString(), is_active: true },
    ], total: 2 });
    render(<ExceptionsPage />);
    await waitFor(() => screen.getByText('cursor.exe'));
    // Select the first entry
    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[1]); // skip header checkbox, click first row
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
  });

  it('calls updateAllowListEntry for each selected entry on extend', async () => {
    const newExpiry = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 16);
    api.fetchAllowList.mockResolvedValue({ items: [
      { id: 'e1', pattern: 'cursor.exe', pattern_type: 'process_name',
        expires_at: new Date(Date.now() + 86400000).toISOString(), is_active: true },
    ], total: 1 });
    api.updateAllowListEntry.mockResolvedValue({ id: 'e1' });
    render(<ExceptionsPage />);
    await waitFor(() => screen.getByText('cursor.exe'));
    await userEvent.click(screen.getAllByRole('checkbox')[1]);
    await userEvent.click(screen.getByRole('button', { name: /extend expiry/i }));
    // Set new expiry date and confirm
    const dateInput = screen.getByLabelText(/new expiry/i);
    await userEvent.type(dateInput, newExpiry);
    await userEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(api.updateAllowListEntry).toHaveBeenCalledWith('e1', expect.objectContaining({ expires_at: expect.any(String) }));
  });
});
```

Run to confirm failure:
```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- ExceptionsPage 2>&1 | tail -10
```

- [ ] **Step 5.2: Add selection + bulk extend**

Follow the same pattern as ApprovalsPage bulk actions:
- Add checkbox column to the allow-list table
- Show bulk action bar when items selected (`{selectedIds.size > 0 && <BulkBar />}`)
- "Extend expiry" action: show a modal with a `datetime-local` input labeled "New expiry"; on confirm call `updateAllowListEntry(id, { expires_at: newDate })` for each selected ID
- Write the action summary (count + action type) to audit log — this happens automatically on each PATCH call since `patch_allow_list_entry` already calls `audit_record`

- [ ] **Step 5.3: Run tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test -- ExceptionsPage 2>&1 | tail -20
```

- [ ] **Step 5.3: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/ExceptionsPage.jsx
git commit -m "feat(dashboard): bulk expiry extension for allow-list entries (O3.1)"
```

---

## Task 6: O3.2 — Operator ergonomics

**Files:**
- Modify: `dashboard/src/pages/ApprovalsPage.jsx` and/or `ExceptionsPage.jsx`

These are polish tasks; implement all in one commit.

### Saved filters

Add filter persistence to ApprovalsPage and ExceptionsPage using `localStorage`. When a filter (status tab, search text, or date range) changes, save to `localStorage.setItem('approvals_filter', JSON.stringify(filter))`. On mount, initialize from stored value.

```javascript
// On filter change:
localStorage.setItem('approvals_status_filter', statusFilter);

// On mount:
const savedFilter = localStorage.getItem('approvals_status_filter') || 'pending';
const [statusFilter, setStatusFilter] = useState(savedFilter);
```

### Keyboard shortcuts

Add `useEffect` with `keydown` listener for modal-heavy interactions:
- `Escape` → close open drawer/modal
- On approvals pending table: `a` key → approve focused item, `d` → deny (nice-to-have; implement if time allows)

```javascript
useEffect(() => {
  function onKey(e) {
    if (e.key === 'Escape') {
      closeDrawer();
      closeModal();
    }
  }
  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}, []);
```

### Standardize empty/error/loading states

Review all new and modified pages. Each page must have:
- Loading state: spinner or skeleton
- Empty state: descriptive message ("No pending approvals")
- Error state: message + retry button

If any page is missing one of these, add it.

- [ ] **Step 6.1: Implement saved filters, keyboard Escape, empty/error/loading standardization**

(Follow the patterns above across ApprovalsPage, ExceptionsPage, MembersPage, OrgSettingsPage.)

- [ ] **Step 6.2: Run all dashboard tests**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test 2>&1 | tail -30
```

Expected: All pass.

- [ ] **Step 6.3: Commit**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance
git add dashboard/src/pages/ApprovalsPage.jsx \
  dashboard/src/pages/ExceptionsPage.jsx \
  dashboard/src/pages/MembersPage.jsx \
  dashboard/src/pages/OrgSettingsPage.jsx
git commit -m "feat(dashboard): saved filters, keyboard shortcuts, standardized states (O3.2)"
```

---

## Task 7: Final verification

- [ ] **Step 7.1: Run full dashboard test suite**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run test 2>&1 | tail -30
```

Expected: All pass.

- [ ] **Step 7.2: Run API tests (ensure no regression from UserUpdate schema changes)**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/api
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All pass.

- [ ] **Step 7.3: Build dashboard (verify no bundle size regression)**

```bash
cd /Users/echance/Documents/Cursor/agentic-governance/dashboard
npm run build 2>&1 | tail -20
```

Check that no chunk exceeds 700KB (CI hard limit from Wave 4 L2).
