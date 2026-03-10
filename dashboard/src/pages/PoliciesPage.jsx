import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import { fetchPolicies, createPolicy, updatePolicy } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';

const DECISION_BADGES = {
  block:             'bg-red-900/40 text-red-400 border-red-700/40',
  approval_required: 'bg-amber-900/40 text-amber-400 border-amber-700/40',
  warn:              'bg-yellow-900/40 text-yellow-400 border-yellow-700/40',
  detect:            'bg-blue-900/40 text-blue-400 border-blue-700/40',
};

export default function PoliciesPage() {
  const { user } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);

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

  const handleToggleActive = async (policy) => {
    try {
      await updatePolicy(policy.id, { is_active: !policy.is_active });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-detec-slate-100">Policies</h1>
        <div className="flex items-center gap-3">
          {loading && <ApertureSpinner size="sm" label="Loading policies" />}
          {canManage && (
            <button
              onClick={() => { setEditingPolicy(null); setShowForm(true); }}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 transition-colors"
            >
              Create policy
            </button>
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
            Policies define how Detec responds to each tool class. Without them, everything stays at Detect.
          </div>
          {canManage && (
            <button
              onClick={() => { setEditingPolicy(null); setShowForm(true); }}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 transition-colors"
            >
              Create your first policy
            </button>
          )}
        </div>
      )}

      {policies.length > 0 && (
        <div className="grid gap-3">
          {policies.map((policy) => (
            <PolicyCard
              key={policy.id}
              policy={policy}
              canManage={canManage}
              onEdit={() => { setEditingPolicy(policy); setShowForm(true); }}
              onToggleActive={() => handleToggleActive(policy)}
            />
          ))}
        </div>
      )}

      {total > 0 && (
        <div className="text-sm text-detec-slate-500 text-center">
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
    </div>
  );
}


function PolicyCard({ policy, canManage, onEdit, onToggleActive }) {
  const decisionState = policy.parameters?.decision_state;
  const badgeClass = DECISION_BADGES[decisionState] || 'bg-detec-slate-800/60 text-detec-slate-400 border-detec-slate-700/40';

  return (
    <div className={`rounded-xl border bg-detec-slate-800/50 p-5 transition-colors ${
      policy.is_active ? 'border-detec-slate-700/50' : 'border-detec-slate-700/30 opacity-60'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-detec-slate-200 font-mono">{policy.rule_id}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-detec-slate-700 text-detec-slate-400">
              v{policy.rule_version}
            </span>
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
          </div>
        )}
      </div>

      {policy.parameters && Object.keys(policy.parameters).length > 0 && (
        <div className="mt-3 pt-3 border-t border-detec-slate-700/50">
          <div className="text-xs text-detec-slate-500 uppercase tracking-wider font-medium mb-1">Parameters</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
            {Object.entries(policy.parameters).map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-1.5 text-xs">
                <span className="text-detec-slate-500 font-mono">{k}:</span>
                <span className="text-detec-slate-300 font-mono truncate">
                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function PolicyFormModal({ policy, onClose, onSaved, onError }) {
  const isEdit = !!policy;
  const [ruleId, setRuleId] = useState(policy?.rule_id || '');
  const [ruleVersion, setRuleVersion] = useState(policy?.rule_version || '0.1.0');
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
        await updatePolicy(policy.id, {
          rule_id: ruleId.trim(),
          rule_version: ruleVersion.trim(),
          description: description.trim() || null,
          is_active: isActive,
          parameters: params,
        });
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
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Rule ID</label>
              <input
                type="text"
                value={ruleId}
                onChange={(e) => setRuleId(e.target.value)}
                placeholder="e.g. ENFORCE-D01"
                className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono focus:border-detec-primary-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-slate-400 mb-1">Version</label>
              <input
                type="text"
                value={ruleVersion}
                onChange={(e) => setRuleVersion(e.target.value)}
                placeholder="0.1.0"
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
