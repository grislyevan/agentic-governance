import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import {
  fetchEndpointProfiles,
  createEndpointProfile,
  updateEndpointProfile,
  deleteEndpointProfile,
  fetchEndpoints,
  getApiConfig,
} from '../lib/api';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';

const POSTURE_OPTIONS = [
  { value: 'passive', label: 'Passive' },
  { value: 'audit', label: 'Audit' },
  { value: 'active', label: 'Active' },
];

export default function EndpointProfilesPage() {
  const { user } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [total, setTotal] = useState(0);
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const canManage = user?.role === 'owner' || user?.role === 'admin';

  const loadProfiles = useCallback(async () => {
    try {
      const config = getApiConfig();
      const data = await fetchEndpointProfiles(config, { pageSize: 200 });
      setProfiles(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadEndpoints = useCallback(async () => {
    try {
      const config = getApiConfig();
      const data = await fetchEndpoints(config);
      setEndpoints(data.items || []);
    } catch {
      setEndpoints([]);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    await Promise.all([loadProfiles(), loadEndpoints()]);
  }, [loadProfiles, loadEndpoints]);

  useEffect(() => {
    load();
  }, [load]);

  const { lastUpdated, paused, togglePause } = usePolling(load);

  const countByProfile = (profileId) =>
    endpoints.filter((e) => e.endpoint_profile_id === profileId).length;

  const handleDelete = (profile) => {
    const count = countByProfile(profile.id);
    if (count > 0) {
      setError(
        `Cannot delete "${profile.name}": ${count} endpoint(s) are assigned. Unassign them first from the AI Inventory page.`
      );
      return;
    }
    setConfirmDelete(profile);
  };

  const handleConfirmDelete = async () => {
    if (!confirmDelete) return;
    setError(null);
    try {
      await deleteEndpointProfile(confirmDelete.id);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setConfirmDelete(null);
    }
  };

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <h1 className="text-xl sm:text-2xl font-bold text-detec-ui-text">
            Endpoint Profiles
          </h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        {canManage && (
          <button
            onClick={() => { setEditingProfile(null); setShowForm(true); }}
            className="rounded-lg bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors"
          >
            Create profile
          </button>
        )}
      </div>

      <p className="text-sm text-detec-ui-muted">
        Profiles define scan interval, enforcement posture, and auto-enforce threshold for groups of endpoints (e.g. Critical Server, Standard Workstation). Assign profiles to endpoints from the AI Inventory page.
      </p>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <ApertureSpinner size="lg" label="Loading profiles" />
        </div>
      ) : profiles.length === 0 ? (
        <div className="rounded-xl border border-dashed border-detec-ui-border bg-detec-slate-50 px-8 py-20 text-center">
          <div className="text-detec-ui-muted text-sm font-medium mb-1">No endpoint profiles yet</div>
          <div className="text-detec-ui-muted text-sm max-w-sm mx-auto mb-4">
            Create profiles to apply consistent scan and enforcement settings to groups of endpoints.
          </div>
          {canManage && (
            <button
              onClick={() => { setEditingProfile(null); setShowForm(true); }}
              className="rounded-lg bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors"
            >
              Create first profile
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-detec-ui-border/50 text-left text-detec-ui-muted">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Slug</th>
                <th className="px-4 py-3 font-medium">Interval</th>
                <th className="px-4 py-3 font-medium">Posture</th>
                <th className="px-4 py-3 font-medium">Threshold</th>
                <th className="px-4 py-3 font-medium">Endpoints</th>
                {canManage && <th className="px-4 py-3 font-medium w-24">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => {
                const assignedCount = countByProfile(p.id);
                return (
                  <tr
                    key={p.id}
                    className="border-b border-detec-ui-border/30 hover:bg-detec-ui-surface/80"
                  >
                    <td className="px-4 py-3 text-detec-ui-text font-medium">{p.name}</td>
                    <td className="px-4 py-3 font-mono text-detec-ui-muted text-xs">{p.slug}</td>
                    <td className="px-4 py-3 text-detec-ui-text">{p.scan_interval_seconds}s</td>
                    <td className="px-4 py-3">
                      <span className="capitalize text-detec-ui-text">{p.enforcement_posture}</span>
                    </td>
                    <td className="px-4 py-3 text-detec-ui-text">{p.auto_enforce_threshold.toFixed(2)}</td>
                    <td className="px-4 py-3 text-detec-ui-muted">
                      {assignedCount > 0 ? (
                        <span>{assignedCount} assigned</span>
                      ) : (
                        <span className="text-detec-ui-muted">0</span>
                      )}
                    </td>
                    {canManage && (
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => { setEditingProfile(p); setShowForm(true); }}
                            className="text-detec-ui-muted hover:text-detec-ui-accent text-xs"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(p)}
                            className="text-detec-ui-muted hover:text-red-400 text-xs"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total > 0 && (
        <div className="text-sm text-detec-ui-muted">
          {total} profile{total !== 1 ? 's' : ''} total
        </div>
      )}

      {showForm && (
        <ProfileFormModal
          profile={editingProfile}
          onClose={() => { setShowForm(false); setEditingProfile(null); }}
          onSaved={() => { setShowForm(false); setEditingProfile(null); load(); }}
          onError={setError}
        />
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setConfirmDelete(null)}>
          <div
            className="w-full max-w-sm rounded-xl border border-detec-ui-border bg-detec-ui-page p-4 sm:p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-detec-ui-text mb-2">Delete profile?</h3>
            <p className="text-sm text-detec-ui-muted mb-5">
              Permanently delete &quot;{confirmDelete.name}&quot;? This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="rounded-lg border border-detec-ui-border px-4 py-2 text-sm text-detec-ui-muted hover:bg-detec-ui-surface"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                className="rounded-lg px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-500"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileFormModal({ profile, onClose, onSaved, onError }) {
  const isEdit = !!profile;
  const [name, setName] = useState(profile?.name ?? '');
  const [slug, setSlug] = useState(profile?.slug ?? '');
  const [scanIntervalSeconds, setScanIntervalSeconds] = useState(
    profile?.scan_interval_seconds ?? 300
  );
  const [enforcementPosture, setEnforcementPosture] = useState(
    profile?.enforcement_posture ?? 'passive'
  );
  const [autoEnforceThreshold, setAutoEnforceThreshold] = useState(
    profile?.auto_enforce_threshold ?? 0.75
  );
  const [policySetId, setPolicySetId] = useState(profile?.policy_set_id ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) {
      setFormError('Name is required');
      return;
    }
    if (scanIntervalSeconds < 30 || scanIntervalSeconds > 86400) {
      setFormError('Scan interval must be between 30 and 86400 seconds');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        slug: slug.trim() || undefined,
        scan_interval_seconds: scanIntervalSeconds,
        enforcement_posture: enforcementPosture,
        auto_enforce_threshold: autoEnforceThreshold,
        policy_set_id: policySetId.trim() || null,
      };
      if (isEdit) {
        await updateEndpointProfile(profile.id, payload);
      } else {
        await createEndpointProfile(payload);
      }
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
        className="w-full max-w-lg rounded-xl border border-detec-ui-border bg-detec-ui-page p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-ui-text mb-4">
          {isEdit ? 'Edit Profile' : 'Create Profile'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Critical Server"
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text focus:border-detec-ui-accent focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Slug
              <span className="text-detec-ui-muted font-normal ml-1">(optional, auto-generated from name if empty)</span>
            </label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="critical-server"
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text font-mono focus:border-detec-ui-accent focus:outline-none"
              maxLength={64}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Scan interval (seconds)
            </label>
            <input
              type="number"
              min={30}
              max={86400}
              value={scanIntervalSeconds}
              onChange={(e) => setScanIntervalSeconds(Number(e.target.value))}
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text focus:border-detec-ui-accent focus:outline-none"
            />
            <p className="text-xs text-detec-ui-muted mt-1">30 to 86400 (24 hours)</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Enforcement posture
            </label>
            <select
              value={enforcementPosture}
              onChange={(e) => setEnforcementPosture(e.target.value)}
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text focus:border-detec-ui-accent focus:outline-none"
            >
              {POSTURE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Auto-enforce threshold
            </label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={autoEnforceThreshold}
              onChange={(e) => setAutoEnforceThreshold(Number(e.target.value))}
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text focus:border-detec-ui-accent focus:outline-none"
            />
            <p className="text-xs text-detec-ui-muted mt-1">0.00 to 1.00</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Policy set ID
              <span className="text-detec-ui-muted font-normal ml-1">(optional)</span>
            </label>
            <input
              type="text"
              value={policySetId}
              onChange={(e) => setPolicySetId(e.target.value)}
              placeholder=""
              className="w-full rounded-lg border border-detec-ui-border bg-detec-ui-surface px-3 py-2 text-sm text-detec-ui-text font-mono focus:border-detec-ui-accent focus:outline-none"
              maxLength={128}
            />
          </div>

          {formError && (
            <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-detec-ui-border px-4 py-2 text-sm text-detec-ui-muted hover:bg-detec-ui-surface"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
            >
              {submitting ? 'Saving...' : isEdit ? 'Save changes' : 'Create profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
