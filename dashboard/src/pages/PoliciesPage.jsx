import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import { fetchPolicies, createPolicy, updatePolicy, deletePolicy, restoreDefaultPolicies } from '../lib/api';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';

const DECISION_BADGES = {
  block:             'bg-red-900/40 text-red-400 border-red-700/40',
  approval_required: 'bg-amber-900/40 text-amber-400 border-amber-700/40',
  warn:              'bg-yellow-900/40 text-yellow-400 border-yellow-700/40',
  detect:            'bg-blue-900/40 text-blue-400 border-blue-700/40',
};

const CATEGORY_LABELS = {
  enforcement: 'Core Enforcement',
  class_d:     'Class D Overrides',
  overlay:     'Overlay Rules',
  fallback:    'Fallback Rules',
};

const CATEGORY_ORDER = ['enforcement', 'class_d', 'overlay', 'fallback'];

function groupByCategory(policies) {
  const groups = {};
  const custom = [];

  for (const p of policies) {
    if (p.category && CATEGORY_ORDER.includes(p.category)) {
      if (!groups[p.category]) groups[p.category] = [];
      groups[p.category].push(p);
    } else {
      custom.push(p);
    }
  }

  const ordered = [];
  for (const cat of CATEGORY_ORDER) {
    if (groups[cat]?.length) {
      ordered.push({ category: cat, label: CATEGORY_LABELS[cat], policies: groups[cat] });
    }
  }
  if (custom.length) {
    ordered.push({ category: 'custom', label: 'Custom Rules', policies: custom });
  }
  return ordered;
}


export default function PoliciesPage() {
  const { user } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [restoring, setRestoring] = useState(false);
  const [confirmDisable, setConfirmDisable] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const canManage = user?.role === 'owner' || user?.role === 'admin';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPolicies();
      setPolicies(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const { lastUpdated, paused, togglePause } = usePolling(load);

  const handleToggleActive = async (policy) => {
    if (policy.is_baseline && policy.is_active) {
      setConfirmDisable(policy);
      return;
    }
    try {
      await updatePolicy(policy.id, { is_active: !policy.is_active });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleConfirmDisable = async () => {
    if (!confirmDisable) return;
    try {
      await updatePolicy(confirmDisable.id, { is_active: false });
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setConfirmDisable(null);
    }
  };

  const handleDelete = async (policy) => {
    if (policy.is_baseline) return;
    setConfirmDelete(policy);
  };

  const handleConfirmDelete = async () => {
    if (!confirmDelete) return;
    try {
      await deletePolicy(confirmDelete.id);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleRestoreDefaults = async () => {
    setRestoring(true);
    setError(null);
    try {
      await restoreDefaultPolicies();
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setRestoring(false);
    }
  };

  const groups = groupByCategory(policies);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-detec-slate-100">Policies</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        <div className="flex items-center gap-3">
          {loading && <ApertureSpinner size="sm" label="Loading policies" />}
          {canManage && (
            <>
              <button
                onClick={handleRestoreDefaults}
                disabled={restoring}
                className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm font-medium text-detec-slate-300 hover:bg-detec-slate-800 hover:text-detec-slate-100 transition-colors disabled:opacity-50"
              >
                {restoring ? 'Restoring...' : 'Restore defaults'}
              </button>
              <button
                onClick={() => { setEditingPolicy(null); setShowForm(true); }}
                className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 transition-colors"
              >
                Create policy
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {policies.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
          <div className="mb-3 opacity-40">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="text-detec-slate-400 text-sm font-medium mb-1">No policies configured yet</div>
          <div className="text-detec-slate-600 text-sm max-w-sm mx-auto mb-4">
            Restore baseline policies to get started with Detec's default enforcement ladder.
          </div>
          {canManage && (
            <button
              onClick={handleRestoreDefaults}
              disabled={restoring}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 transition-colors disabled:opacity-50"
            >
              {restoring ? 'Restoring...' : 'Restore baseline policies'}
            </button>
          )}
        </div>
      )}

      {groups.map((group) => (
        <div key={group.category} className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-detec-slate-500 pt-2">
            {group.label}
            <span className="ml-2 text-xs font-normal text-detec-slate-600">
              ({group.policies.length})
            </span>
          </h2>
          <div className="grid gap-3">
            {group.policies.map((policy) => (
              <PolicyCard
                key={policy.id}
                policy={policy}
                canManage={canManage}
                onEdit={() => { setEditingPolicy(policy); setShowForm(true); }}
                onToggleActive={() => handleToggleActive(policy)}
                onDelete={() => handleDelete(policy)}
              />
            ))}
          </div>
        </div>
      ))}

      {total > 0 && (
        <div className="text-sm text-detec-slate-500 text-center pt-2">
          {total} {total === 1 ? 'policy' : 'policies'} total
        </div>
      )}

      {showForm && (
        <PolicyFormModal
          policy={editingPolicy}
          onClose={() => { setShowForm(false); setEditingPolicy(null); }}
          onSaved={() => { setShowForm(false); setEditingPolicy(null); load(); }}
          onError={setError}
        />
      )}

      {confirmDisable && (
        <ConfirmModal
          title="Disable baseline policy?"
          message={
            `${confirmDisable.rule_id} is a baseline enforcement rule. ` +
            'Disabling it may reduce your security posture. Are you sure?'
          }
          confirmLabel="Disable"
          confirmClass="bg-amber-600 hover:bg-amber-500"
          onConfirm={handleConfirmDisable}
          onCancel={() => setConfirmDisable(null)}
        />
      )}

      {confirmDelete && (
        <ConfirmModal
          title="Delete policy?"
          message={`Permanently delete custom policy "${confirmDelete.rule_id}"? This cannot be undone.`}
          confirmLabel="Delete"
          confirmClass="bg-red-600 hover:bg-red-500"
          onConfirm={handleConfirmDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}


function PolicyCard({ policy, canManage, onEdit, onToggleActive, onDelete }) {
  const decisionState = policy.parameters?.decision_state;
  const badgeClass = DECISION_BADGES[decisionState] || 'bg-detec-slate-800/60 text-detec-slate-400 border-detec-slate-700/40';
  const isInactiveBaseline = policy.is_baseline && !policy.is_active;

  return (
    <div className={`rounded-xl border bg-detec-slate-800/50 p-5 transition-colors ${
      policy.is_active ? 'border-detec-slate-700/50' : 'border-detec-slate-700/30 opacity-60'
    } ${isInactiveBaseline ? 'ring-1 ring-amber-700/30' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-detec-slate-200 font-mono">{policy.rule_id}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-detec-slate-700 text-detec-slate-400">
              v{policy.rule_version}
            </span>
            {policy.is_baseline && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-detec-primary-900/40 text-detec-primary-400 border border-detec-primary-700/30">
                Baseline
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              policy.is_active ? 'bg-detec-teal-500/15 text-detec-teal-500' : 'bg-detec-slate-700 text-detec-slate-500'
            }`}>
              {policy.is_active ? 'Active' : 'Inactive'}
            </span>
            {decisionState && (
              <span className={`inline-block rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass}`}>
                {decisionState.replace('_', ' ')}
              </span>
            )}
          </div>
          {policy.description && (
            <p className="text-sm text-detec-slate-400 mt-1">{policy.description}</p>
          )}
          {isInactiveBaseline && (
            <p className="text-xs text-amber-500/80 mt-1.5">
              This baseline rule is disabled. Your enforcement posture may be reduced.
            </p>
          )}
        </div>

        {canManage && (
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={onEdit}
              className="rounded px-2 py-1 text-xs text-detec-slate-400 hover:bg-detec-slate-700 hover:text-detec-slate-200 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={onToggleActive}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                policy.is_active
                  ? 'text-amber-400 hover:bg-amber-950/40'
                  : 'text-emerald-400 hover:bg-emerald-950/40'
              }`}
            >
              {policy.is_active ? 'Disable' : 'Enable'}
            </button>
            {!policy.is_baseline && (
              <button
                onClick={onDelete}
                className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950/40 transition-colors"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>

      {policy.parameters && Object.keys(policy.parameters).length > 0 && (
        <PolicyParameters parameters={policy.parameters} />
      )}
    </div>
  );
}


function PolicyParameters({ parameters }) {
  const { decision_state, conditions, precedence, overlay, is_fallback, rationale, ...rest } = parameters;

  const conditionEntries = conditions ? Object.entries(conditions) : [];
  const hasExtra = Object.keys(rest).length > 0;

  if (!conditionEntries.length && !rationale && !hasExtra) return null;

  return (
    <div className="mt-3 pt-3 border-t border-detec-slate-700/50">
      {conditionEntries.length > 0 && (
        <div className="mb-2">
          <div className="text-xs text-detec-slate-500 uppercase tracking-wider font-medium mb-1">Conditions</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
            {conditionEntries.map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-1.5 text-xs">
                <span className="text-detec-slate-500 font-mono">{k}:</span>
                <span className="text-detec-slate-300 font-mono truncate">
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {rationale && (
        <p className="text-xs text-detec-slate-500 italic mt-1">{rationale}</p>
      )}
      {hasExtra && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mt-1">
          {Object.entries(rest).map(([k, v]) => (
            <div key={k} className="flex items-baseline gap-1.5 text-xs">
              <span className="text-detec-slate-500 font-mono">{k}:</span>
              <span className="text-detec-slate-300 font-mono truncate">
                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function PolicyFormModal({ policy, onClose, onSaved, onError }) {
  const isEdit = !!policy;
  const isBaseline = policy?.is_baseline;
  const [ruleId, setRuleId] = useState(policy?.rule_id || '');
  const [ruleVersion, setRuleVersion] = useState(policy?.rule_version || '0.4.0');
  const [description, setDescription] = useState(policy?.description || '');
  const [isActive, setIsActive] = useState(policy?.is_active ?? true);
  const [paramsText, setParamsText] = useState(
    policy?.parameters ? JSON.stringify(policy.parameters, null, 2) : '{\n  \n}'
  );
  const [paramsError, setParamsError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const validateParams = (text) => {
    try {
      JSON.parse(text);
      setParamsError(null);
      return true;
    } catch (e) {
      setParamsError(e.message);
      return false;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);

    if (!ruleId.trim()) {
      setFormError('Rule ID is required');
      return;
    }
    if (!validateParams(paramsText)) {
      setFormError('Parameters must be valid JSON');
      return;
    }

    setSubmitting(true);
    try {
      const params = JSON.parse(paramsText);
      if (isEdit) {
        const payload = {
          rule_version: ruleVersion.trim(),
          description: description.trim() || null,
          is_active: isActive,
          parameters: params,
        };
        if (!isBaseline) {
          payload.rule_id = ruleId.trim();
        }
        await updatePolicy(policy.id, payload);
      } else {
        await createPolicy({
          rule_id: ruleId.trim(),
          rule_version: ruleVersion.trim(),
          description: description.trim() || null,
          is_active: isActive,
          parameters: params,
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
        className="w-full max-w-lg rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">
          {isEdit ? 'Edit Policy' : 'Create Policy'}
          {isBaseline && (
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-detec-primary-900/40 text-detec-primary-400 border border-detec-primary-700/30 align-middle">
              Baseline
            </span>
          )}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Rule ID</label>
              <input
                type="text"
                value={ruleId}
                onChange={(e) => setRuleId(e.target.value)}
                placeholder="e.g. CUSTOM-001"
                disabled={isBaseline}
                className={`w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono focus:border-detec-primary-500 focus:outline-none ${
                  isBaseline ? 'opacity-50 cursor-not-allowed' : ''
                }`}
                required
              />
              {isBaseline && (
                <p className="text-xs text-detec-slate-600 mt-1">Rule ID is locked on baseline policies</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Version</label>
              <input
                type="text"
                value={ruleVersion}
                onChange={(e) => setRuleVersion(e.target.value)}
                placeholder="0.4.0"
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono focus:border-detec-primary-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this policy does"
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-3">
            <label className="relative inline-flex cursor-pointer items-center">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="peer sr-only"
              />
              <div className="h-5 w-9 rounded-full bg-detec-slate-700 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-detec-slate-400 after:transition-all peer-checked:bg-detec-primary-600 peer-checked:after:translate-x-full peer-checked:after:bg-white" />
            </label>
            <span className="text-sm text-detec-slate-300">
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">
              Parameters
              <span className="text-detec-slate-600 font-normal ml-1">(JSON)</span>
            </label>
            <textarea
              value={paramsText}
              onChange={(e) => { setParamsText(e.target.value); setParamsError(null); }}
              onBlur={() => validateParams(paramsText)}
              rows={8}
              spellCheck={false}
              className={`w-full rounded-lg border bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono focus:outline-none resize-y ${
                paramsError
                  ? 'border-red-700 focus:border-red-500'
                  : 'border-detec-slate-700 focus:border-detec-primary-500'
              }`}
            />
            {paramsError && (
              <p className="mt-1 text-xs text-red-400">Invalid JSON: {paramsError}</p>
            )}
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
              className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 disabled:opacity-50"
            >
              {submitting ? 'Saving...' : isEdit ? 'Save changes' : 'Create policy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


function ConfirmModal({ title, message, confirmLabel, confirmClass, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div
        className="w-full max-w-sm rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-detec-slate-100 mb-2">{title}</h3>
        <p className="text-sm text-detec-slate-400 mb-5">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
