import { useState } from 'react';
import { updateEndpoint } from '../../lib/api';
import useAuth from '../../hooks/useAuth';

function timeSince(date) {
  if (!date) return 'Never';
  const d = new Date(date);
  const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days !== 1 ? 's' : ''} ago`;
}

export default function EndpointsTable({ endpoints, profiles, onUpdate }) {
  const { user } = useAuth();
  const canManage = user?.role === 'owner' || user?.role === 'admin';

  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkProfileId, setBulkProfileId] = useState('');
  const [updatingId, setUpdatingId] = useState(null);
  const [bulkUpdating, setBulkUpdating] = useState(false);
  const [error, setError] = useState(null);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === endpoints.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(endpoints.map((e) => e.id)));
    }
  };

  const handleRowProfileChange = async (endpointId, profileId) => {
    setUpdatingId(endpointId);
    setError(null);
    try {
      await updateEndpoint(endpointId, {
        endpoint_profile_id: profileId === '' ? '' : profileId,
      });
      onUpdate?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleBulkAssign = async () => {
    if (selectedIds.size === 0) return;
    setBulkUpdating(true);
    setError(null);
    try {
      const value = bulkProfileId === '' ? '' : bulkProfileId;
      await Promise.all(
        Array.from(selectedIds).map((id) =>
          updateEndpoint(id, { endpoint_profile_id: value })
        )
      );
      setSelectedIds(new Set());
      setBulkProfileId('');
      onUpdate?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBulkUpdating(false);
    }
  };

  const profileName = (profileId) => {
    if (!profileId) return 'No profile';
    const p = (profiles || []).find((x) => x.id === profileId);
    return p?.name ?? profileId;
  };

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold text-detec-ui-text">Endpoints</h2>
      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}
      <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-detec-ui-border/50 text-left text-detec-ui-muted">
              {canManage && (
                <th className="px-3 py-2 w-10">
                  <input
                    type="checkbox"
                    checked={endpoints.length > 0 && selectedIds.size === endpoints.length}
                    onChange={toggleSelectAll}
                    aria-label="Select all"
                    className="rounded border-detec-ui-border bg-detec-ui-surface text-detec-ui-accent focus:ring-detec-ui-accent"
                  />
                </th>
              )}
              <th className="px-3 py-2 font-medium">Hostname</th>
              <th className="px-3 py-2 font-medium">Profile</th>
              <th className="px-3 py-2 font-medium">Management</th>
              <th className="px-3 py-2 font-medium">Last seen</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.map((ep) => (
              <tr
                key={ep.id}
                className="border-b border-detec-ui-border/30 hover:bg-detec-ui-surface/80"
              >
                {canManage && (
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(ep.id)}
                      onChange={() => toggleSelect(ep.id)}
                      aria-label={`Select ${ep.hostname}`}
                      className="rounded border-detec-ui-border bg-detec-ui-surface text-detec-ui-accent focus:ring-detec-ui-accent"
                    />
                  </td>
                )}
                <td className="px-3 py-2 font-medium text-detec-ui-text">{ep.hostname}</td>
                <td className="px-3 py-2">
                  {canManage ? (
                    <select
                      value={ep.endpoint_profile_id ?? ''}
                      onChange={(e) => handleRowProfileChange(ep.id, e.target.value)}
                      disabled={updatingId === ep.id}
                      className="rounded border border-detec-ui-border bg-detec-ui-surface px-2 py-1 text-xs text-detec-ui-text focus:border-detec-ui-accent focus:outline-none disabled:opacity-50"
                    >
                      <option value="">No profile</option>
                      {(profiles || []).map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-detec-ui-muted">{profileName(ep.endpoint_profile_id)}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-detec-ui-muted">
                  {ep.management_state === 'managed' ? 'Conformant' : 'Nonconformant'}
                </td>
                <td className="px-3 py-2 text-detec-ui-muted text-xs">
                  {timeSince(ep.last_seen_at)}
                  {ep.computed_status === 'tamper_suspected' && (
                    <span className="ml-2 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-red-950/60 text-red-400 border border-red-800/50">
                      Tamper Alert
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canManage && selectedIds.size > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-detec-ui-muted">
            {selectedIds.size} selected
          </span>
          <select
            value={bulkProfileId}
            onChange={(e) => setBulkProfileId(e.target.value)}
            className="rounded border border-detec-ui-border bg-detec-ui-surface px-3 py-1.5 text-sm text-detec-ui-text focus:border-detec-ui-accent focus:outline-none"
          >
            <option value="">No profile</option>
            {(profiles || []).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button
            onClick={handleBulkAssign}
            disabled={bulkUpdating}
            className="rounded-lg bg-detec-ui-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
          >
            {bulkUpdating ? 'Updating...' : 'Assign selected'}
          </button>
        </div>
      )}
    </div>
  );
}
