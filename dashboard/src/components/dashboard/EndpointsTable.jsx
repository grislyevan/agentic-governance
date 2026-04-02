import { useState } from 'react';
import { updateEndpoint, generateUninstallToken, decommissionEndpoint, rotateEndpointAgentKey } from '../../lib/api';
import useAuth from '../../hooks/useAuth';

const TELEMETRY_BADGE = {
  ESF:     { label: 'Native (ESF)',  cls: 'bg-detec-teal-500/15 text-detec-teal-500 border-detec-teal-500/30' },
  ETW:     { label: 'Native (ETW)',  cls: 'bg-detec-teal-500/15 text-detec-teal-500 border-detec-teal-500/30' },
  eBPF:    { label: 'Native (eBPF)', cls: 'bg-detec-teal-500/15 text-detec-teal-500 border-detec-teal-500/30' },
  polling: { label: 'Polling',       cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
};

function TelemetryBadge({ provider }) {
  if (!provider) return <span className="text-detec-ui-muted text-xs">—</span>;
  const badge = TELEMETRY_BADGE[provider] ?? { label: provider, cls: 'bg-detec-ui-surface text-detec-ui-muted border-detec-ui-border' };
  return (
    <span
      title={provider === 'polling'
        ? 'psutil polling — higher latency, lower signal fidelity. Deploy ESF/ETW for native telemetry.'
        : `Native OS telemetry active (${provider}) — full process/network/file event fidelity.`}
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium ${badge.cls}`}
    >
      {badge.label}
    </span>
  );
}

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

  const [showTokenModal, setShowTokenModal] = useState(false);
  const [uninstallToken, setUninstallToken] = useState('');
  const [tokenHostname, setTokenHostname] = useState('');

  const [showKeyModal, setShowKeyModal] = useState(false);
  const [rotatedKey, setRotatedKey] = useState('');
  const [rotatedKeyHostname, setRotatedKeyHostname] = useState('');
  const [rotatingId, setRotatingId] = useState(null);
  const [keyCopied, setKeyCopied] = useState(false);
  const [copied, setCopied] = useState(false);

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

  const handleGetUninstallToken = async (ep) => {
    setError(null);
    try {
      const data = await generateUninstallToken(ep.id);
      setUninstallToken(data.uninstall_token);
      setTokenHostname(ep.hostname);
      setCopied(false);
      setShowTokenModal(true);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDecommission = async (ep) => {
    if (!window.confirm(`Decommission "${ep.hostname}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await decommissionEndpoint(ep.id);
      onUpdate?.();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleRotateKey = async (ep) => {
    if (!window.confirm(
      `Rotate the agent key for "${ep.hostname}"?\n\nThe agent on this endpoint will need to be reconfigured with the new key.`
    )) return;
    setError(null);
    setRotatingId(ep.id);
    try {
      const data = await rotateEndpointAgentKey(ep.id);
      setRotatedKey(data.agent_key);
      setRotatedKeyHostname(ep.hostname);
      setKeyCopied(false);
      setShowKeyModal(true);
      onUpdate?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setRotatingId(null);
    }
  };

  const uninstallCommand = `msiexec /x DetecAgent.msi UNINSTALL_KEY=${uninstallToken}`;

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(uninstallCommand).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold text-detec-ui-text">Endpoints</h2>
      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}
      <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-800 overflow-hidden">
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
              <th className="px-3 py-2 font-medium hidden sm:table-cell">Host OS</th>
              <th className="px-3 py-2 font-medium">Profile</th>
              <th className="px-3 py-2 font-medium">Management</th>
              <th className="px-3 py-2 font-medium hidden md:table-cell">Telemetry</th>
              <th className="px-3 py-2 font-medium">Last seen</th>
              {canManage && <th className="px-3 py-2 font-medium">Actions</th>}
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
                <td className="px-3 py-2 text-detec-ui-muted text-xs hidden sm:table-cell">{ep.os_info || '—'}</td>
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
                <td className="px-3 py-2 hidden md:table-cell">
                  <TelemetryBadge provider={ep.telemetry_provider} />
                </td>
                <td className="px-3 py-2 text-detec-ui-muted text-xs">
                  {timeSince(ep.last_seen_at)}
                  {ep.computed_status === 'tamper_suspected' && (
                    <span className="ml-2 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-red-950/60 text-red-400 border border-red-800/50">
                      Tamper Alert
                    </span>
                  )}
                </td>
                {canManage && (
                  <td className="px-3 py-2">
                    {ep.status !== 'decommissioned' ? (
                      <div className="flex flex-wrap gap-1">
                        <button
                          onClick={() => handleGetUninstallToken(ep)}
                          className="rounded border border-detec-ui-border bg-detec-ui-surface px-2 py-1 text-xs text-detec-ui-text hover:bg-detec-ui-surface/80 hover:border-detec-ui-accent transition-colors"
                        >
                          Get Uninstall Token
                        </button>
                        <button
                          onClick={() => handleRotateKey(ep)}
                          disabled={rotatingId === ep.id}
                          title="Generate a new per-endpoint agent key"
                          className="rounded border border-amber-700/50 bg-amber-950/20 px-2 py-1 text-xs text-amber-400 hover:bg-amber-950/40 disabled:opacity-50 transition-colors"
                        >
                          {rotatingId === ep.id ? 'Rotating…' : 'Rotate Key'}
                        </button>
                        <button
                          onClick={() => handleDecommission(ep)}
                          className="rounded border border-red-800/50 bg-red-950/30 px-2 py-1 text-xs text-red-400 hover:bg-red-950/60 transition-colors"
                        >
                          Decommission
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-detec-ui-muted italic">Decommissioned</span>
                    )}
                  </td>
                )}
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

      {showTokenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-lg rounded-lg border border-detec-ui-border bg-detec-slate-800 p-6 shadow-xl">
            <h3 className="mb-4 text-sm font-semibold text-detec-ui-text">
              Uninstall Token for {tokenHostname}
            </h3>
            <p className="mb-2 text-xs text-detec-ui-muted">Run the following command on the endpoint to uninstall the agent:</p>
            <div className="mb-4 rounded border border-detec-ui-border bg-detec-ui-surface px-3 py-2 font-mono text-xs text-detec-ui-text break-all select-all">
              {uninstallCommand}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCopyCommand}
                className="rounded-lg bg-detec-ui-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors"
              >
                {copied ? 'Copied!' : 'Copy Command'}
              </button>
              <button
                onClick={() => setShowTokenModal(false)}
                className="rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-1.5 text-sm font-medium text-detec-ui-text hover:bg-detec-ui-surface/80 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-lg rounded-lg border border-amber-700/40 bg-detec-slate-800 p-6 shadow-xl">
            <h3 className="mb-1 text-sm font-semibold text-detec-ui-text">
              New Agent Key — {rotatedKeyHostname}
            </h3>
            <p className="mb-3 text-xs text-amber-400">
              This key is shown once and cannot be retrieved again. Copy it now and reconfigure
              the agent on this endpoint.
            </p>
            <div className="mb-4 rounded border border-amber-700/40 bg-detec-ui-surface px-3 py-2 font-mono text-xs text-detec-ui-text break-all select-all">
              {rotatedKey}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(rotatedKey).then(() => {
                    setKeyCopied(true);
                    setTimeout(() => setKeyCopied(false), 2000);
                  });
                }}
                className="rounded-lg bg-amber-700 hover:bg-amber-600 px-3 py-1.5 text-sm font-medium text-white transition-colors"
              >
                {keyCopied ? 'Copied!' : 'Copy Key'}
              </button>
              <button
                onClick={() => { setShowKeyModal(false); setRotatedKey(''); }}
                className="rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-1.5 text-sm font-medium text-detec-ui-text hover:bg-detec-ui-surface/80 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
