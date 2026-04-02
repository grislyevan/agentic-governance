import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import { fetchPolicies, createPolicy, updatePolicy, deletePolicy, restoreDefaultPolicies, fetchPolicyPresets, applyPolicyPreset } from '../lib/api';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';
import PolicySimPacks from '../components/policy-studio/PolicySimPacks';
import ApiErrorBanner from '../components/ui/ApiErrorBanner';
import PolicyHistoryDrawer from '../components/dashboard/PolicyHistoryDrawer';

const DECISION_BADGES = {
  block:             'bg-red-100 text-red-700 border-red-200',
  approval_required: 'bg-amber-100 text-amber-700 border-amber-200',
  warn:              'bg-yellow-100 text-yellow-700 border-yellow-200',
  detect:            'bg-blue-100 text-detec-ui-accent border-blue-200',
};

const CATEGORY_LABELS = {
  enforcement: 'Core Enforcement',
  class_d:     'Class D Overrides',
  overlay:     'Overlay Rules',
  fallback:    'Fallback Rules',
};

const CATEGORY_ORDER = ['enforcement', 'class_d', 'overlay', 'fallback'];

/** Short human-readable labels for baseline rule IDs (optional display). */
const RULE_ID_LABELS = {
  'ENFORCE-001': 'Low confidence, read-only',
  'ENFORCE-002': 'Medium confidence, scoped write',
  'ENFORCE-003': 'Sensitive assets, approval',
  'ENFORCE-004': 'High confidence, block',
  'ENFORCE-005': 'Crown-jewel deny',
  'ENFORCE-006': 'Autonomous (Class C) approval',
  'ENFORCE-D01': 'Class D block',
  'ENFORCE-D02': 'Class D approval',
  'ENFORCE-D03': 'Class D warn floor',
  'NET-001': 'Unknown outbound approval',
  'NET-002': 'High-volume outbound block',
  'ISO-001': 'Container isolation',
  'ENFORCE-001-F': 'Fallback low',
  'ENFORCE-002-F': 'Fallback medium/high',
  'ENFORCE-003-F': 'Fallback high R3',
};

/** Plain-English summary for baseline rules (hover + detail modal). */
const BASELINE_EXPLAINERS = {
  'ENFORCE-001':
    'When the tool looks low risk and only reads data, we record it and keep watching. No pop-ups for the user.',
  'ENFORCE-002':
    'Medium-confidence use with limited writes gets a warning so people know something happened. Good for coaching without blocking work.',
  'ENFORCE-003':
    'On sensitive systems or bigger changes, we pause until someone approves. Stops risky moves on important assets.',
  'ENFORCE-004':
    'High-confidence misuse or dangerous actions are blocked right away. Use when you trust the score and need a hard stop.',
  'ENFORCE-005':
    'Crown-jewel or regulated assets: block even if confidence is low. Assumes nothing is safe on those machines.',
  'ENFORCE-006':
    'Class C tools (long-running but not fully autonomous) that try risky writes need approval first.',
  'ENFORCE-D01':
    'Always-on autonomous agents (Class D) with broad or admin-like powers are blocked. Stops self-driving daemons from doing the worst actions.',
  'ENFORCE-D02':
    'Class D agents at medium or high confidence that write to disk or APIs need human sign-off. Routine writes are not trusted from daemons.',
  'ENFORCE-D03':
    'Any Class D detection triggers at least a warning. There is no silent allow for always-on autonomous tooling.',
  'NET-001':
    'Outbound connections to unknown destinations need approval so shadow APIs and data exfil are harder.',
  'NET-002':
    'Very chatty or high-volume outbound traffic is blocked to catch bulk export or bot behavior.',
  'ISO-001':
    'Optional rule for container or isolation scenarios. Ships inactive until you turn it on for your environment.',
  'ENFORCE-001-F':
    'Catch-all: low-signal cases still get logged so nothing disappears between specific rules.',
  'ENFORCE-002-F':
    'Fallback when medium or high confidence did not match a tighter rule. Usually warn or escalate.',
  'ENFORCE-003-F':
    'Fallback for high-risk actions that slipped past earlier rules. Often approval or block.',
};

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
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState('');
  const [applyingPreset, setApplyingPreset] = useState(false);
  const [explainerRuleId, setExplainerRuleId] = useState(null);
  const [simPacksOpen, setSimPacksOpen] = useState(false);
  const [historyPolicy, setHistoryPolicy] = useState(null);
  const navigate = useNavigate();

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

  const loadPresets = useCallback(async () => {
    try {
      const data = await fetchPolicyPresets();
      const list = data.presets || [];
      setPresets(list);
      setSelectedPresetId((prev) => (prev || list[0]?.id || ''));
    } catch {
      // Non-fatal; presets section can stay empty
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadPresets(); }, [loadPresets]);

  const { lastUpdated, paused, togglePause } = usePolling(load);

  const handleApplyPreset = async () => {
    if (!selectedPresetId) return;
    setApplyingPreset(true);
    setError(null);
    try {
      await applyPolicyPreset(selectedPresetId);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setApplyingPreset(false);
    }
  };

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
    <div className="space-y-4 min-w-0">
      {/* Policy Simulation Packs — collapsible section */}
      <div className="rounded-detec-lg border border-detec-ui-border bg-detec-ui-surface shadow-detec-sm">
        <button
          type="button"
          onClick={() => setSimPacksOpen((o) => !o)}
          className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-detec-slate-100/60 transition-colors rounded-detec-lg"
          aria-expanded={simPacksOpen}
        >
          <div className="flex items-center gap-2.5">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="text-sm font-semibold text-detec-ui-text">Policy Simulation Packs</span>
            <span className="text-xs text-detec-ui-muted font-normal">guided deployment profiles</span>
          </div>
          <svg
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
            className={`text-detec-ui-muted transition-transform duration-200 ${simPacksOpen ? 'rotate-180' : ''}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {simPacksOpen && (
          <div className="px-5 pb-5 pt-1 border-t border-detec-ui-border/50">
            <PolicySimPacks onApplied={load} />
          </div>
        )}
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <h1 className="text-xl sm:text-2xl font-bold text-detec-ui-text">Policies</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        <div className="flex items-center gap-3">
          {loading && <ApertureSpinner size="sm" label="Loading policies" />}
          {canManage && (
            <>
              <button
                onClick={handleRestoreDefaults}
                disabled={restoring}
                className="rounded-detec border border-detec-ui-border px-4 py-2 text-sm font-medium text-detec-ui-text hover:bg-detec-slate-100 transition-colors disabled:opacity-50"
              >
                {restoring ? 'Restoring...' : 'Restore defaults'}
              </button>
              <button
                onClick={() => navigate('/policies/new')}
                className="rounded-detec bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors"
              >
                Create policy
              </button>
              <button
                type="button"
                onClick={() => { setEditingPolicy(null); setShowForm(true); }}
                className="rounded-detec border border-detec-ui-border px-4 py-2 text-sm font-medium text-detec-ui-muted hover:bg-detec-slate-100 transition-colors"
              >
                Advanced / legacy editor
              </button>
            </>
          )}
        </div>
      </div>

      {presets.length > 0 && (
        <div className="rounded-detec-lg border border-detec-ui-border bg-detec-ui-surface p-4 space-y-3 shadow-detec-card">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-detec-ui-muted">
            Policy preset
          </h2>
          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <div className="flex-1 min-w-0">
              <label htmlFor="preset-select" className="block text-xs font-medium text-detec-ui-muted mb-1">
                Predefined policy
              </label>
              <select
                id="preset-select"
                value={selectedPresetId}
                onChange={(e) => setSelectedPresetId(e.target.value)}
                className="w-full rounded-detec border border-detec-ui-border bg-white px-3 py-2 text-sm text-detec-ui-text focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent focus:outline-none shadow-detec-sm"
              >
                <option value="">Select a preset</option>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {selectedPresetId && (
                <p className="text-xs text-detec-ui-muted mt-1.5">
                  {presets.find((p) => p.id === selectedPresetId)?.description}
                </p>
              )}
            </div>
            {canManage && (
              <button
                type="button"
                onClick={handleApplyPreset}
                disabled={!selectedPresetId || applyingPreset}
                className="rounded-detec bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors disabled:opacity-50 shrink-0"
              >
                {applyingPreset ? 'Applying...' : 'Apply this policy'}
              </button>
            )}
          </div>
        </div>
      )}

      <ApiErrorBanner error={error} onDismiss={() => setError(null)} />

      {policies.length === 0 && !loading && !error && (
        <div className="rounded-detec-lg border border-dashed border-detec-ui-border bg-detec-ui-surface px-8 py-20 text-center shadow-detec-sm">
          <div className="mb-3 opacity-40">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="text-detec-ui-muted text-sm font-medium mb-1">No policies configured yet</div>
          <div className="text-detec-ui-muted text-sm max-w-sm mx-auto mb-4">
            Restore baseline policies to get started with Detec's default enforcement ladder.
          </div>
          {canManage && (
            <button
              onClick={handleRestoreDefaults}
              disabled={restoring}
              className="rounded-detec bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover transition-colors disabled:opacity-50"
            >
              {restoring ? 'Restoring...' : 'Restore baseline policies'}
            </button>
          )}
        </div>
      )}

      {policies.length > 0 && (
        <div className="rounded-detec-md border border-detec-ui-border bg-detec-ui-surface shadow-detec-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-detec-ui-border bg-detec-slate-50/80">
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Name</th>
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Severity</th>
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Outcome</th>
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Source</th>
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-detec-ui-text">Category</th>
                  {canManage && <th className="text-right py-3 px-4 font-semibold text-detec-ui-text">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {policies.map((policy) => (
                  <tr key={policy.id} className="border-b border-detec-ui-border last:border-b-0 hover:bg-detec-slate-50/50">
                    <td className="py-3 px-4">
                      <div className="flex items-start gap-2 max-w-md">
                        <span className="font-medium text-detec-ui-text shrink-0">{policy.rule_id}</span>
                        {policy.is_baseline && BASELINE_EXPLAINERS[policy.rule_id] && (
                          <button
                            type="button"
                            title={BASELINE_EXPLAINERS[policy.rule_id]}
                            onClick={() => setExplainerRuleId(policy.rule_id)}
                            className="shrink-0 w-6 h-6 rounded-full border border-detec-ui-border text-detec-ui-muted hover:text-detec-ui-accent hover:border-detec-ui-accent/50 text-xs font-semibold leading-none flex items-center justify-center"
                            aria-label={`Plain-language summary for ${policy.rule_id}`}
                          >
                            ?
                          </button>
                        )}
                      </div>
                      {policy.description && (
                        <p className="text-xs text-detec-ui-muted mt-1 line-clamp-2">{policy.description}</p>
                      )}
                    </td>
                    <td className="py-3 px-4 text-detec-ui-text">{policy.parameters?.severity ?? '—'}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${DECISION_BADGES[policy.parameters?.decision_state] || 'bg-detec-slate-100 text-detec-ui-muted border-detec-ui-border'}`}>
                        {(policy.parameters?.decision_state || '—').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-detec-ui-muted">{policy.parameters?.source_type ?? '—'}</td>
                    <td className="py-3 px-4">
                      <span className={policy.is_active ? 'text-detec-teal-600 font-medium' : 'text-detec-ui-muted'}>
                        {policy.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-detec-ui-muted">{CATEGORY_LABELS[policy.category] || policy.category || '—'}</td>
                    {canManage && (
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => { setEditingPolicy(policy); setShowForm(true); }}
                            className="rounded px-2 py-1 text-xs text-detec-ui-muted hover:bg-detec-slate-100 hover:text-detec-ui-text"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => setHistoryPolicy(policy)}
                            className="rounded px-2 py-1 text-xs text-detec-ui-muted hover:bg-detec-slate-100 hover:text-detec-ui-accent"
                            title="View change history"
                          >
                            History
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleActive(policy)}
                            className={`rounded px-2 py-1 text-xs ${policy.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-emerald-600 hover:bg-emerald-50'}`}
                          >
                            {policy.is_active ? 'Disable' : 'Enable'}
                          </button>
                          {!policy.is_baseline && (
                            <button
                              type="button"
                              onClick={() => handleDelete(policy)}
                              className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 border-t border-detec-ui-border text-xs text-detec-ui-muted">
            {total} {total === 1 ? 'policy' : 'policies'} total
          </div>
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

      {explainerRuleId && BASELINE_EXPLAINERS[explainerRuleId] && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setExplainerRuleId(null)}
          role="presentation"
        >
          <div
            className="w-full max-w-md rounded-xl border border-detec-ui-border bg-detec-ui-page p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="explainer-title"
          >
            <h3 id="explainer-title" className="text-lg font-semibold text-detec-ui-text mb-2">
              {explainerRuleId}
            </h3>
            <p className="text-sm text-detec-ui-text leading-relaxed mb-3">
              {BASELINE_EXPLAINERS[explainerRuleId]}
            </p>
            <p className="text-xs text-detec-ui-muted mb-4">
              Full definitions live in the governance playbook (section 6.3 baseline ladder).
            </p>
            <button
              type="button"
              onClick={() => setExplainerRuleId(null)}
              className="px-4 py-2 rounded-lg bg-detec-ui-accent text-white text-sm font-medium"
            >
              Close
            </button>
          </div>
        </div>
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

      {historyPolicy && (
        <PolicyHistoryDrawer
          policy={historyPolicy}
          onClose={() => setHistoryPolicy(null)}
        />
      )}
    </div>
  );
}


function PolicyCard({ policy, ruleLabel, canManage, onEdit, onToggleActive, onDelete }) {
  const decisionState = policy.parameters?.decision_state;
  const badgeClass = DECISION_BADGES[decisionState] || 'bg-detec-slate-100 text-detec-ui-muted border-detec-ui-border';
  const isInactiveBaseline = policy.is_baseline && !policy.is_active;

  return (
    <div className={`rounded-detec-lg border bg-detec-ui-surface p-5 transition-colors shadow-detec-card ${
      policy.is_active ? 'border-detec-ui-border' : 'border-detec-ui-border opacity-60'
    } ${isInactiveBaseline ? 'ring-1 ring-amber-300' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-detec-ui-text font-mono">{policy.rule_id}</span>
            {ruleLabel && (
              <span className="text-xs text-detec-ui-muted font-normal">
                {ruleLabel}
              </span>
            )}
            <span className="text-xs px-1.5 py-0.5 rounded bg-detec-slate-100 text-detec-ui-muted">
              v{policy.rule_version}
            </span>
            {policy.is_baseline && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-detec-ui-accent/15 text-detec-ui-accent border border-detec-ui-accent/30">
                Baseline
              </span>
            )}
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              policy.is_active ? 'bg-detec-teal-500/15 text-detec-teal-600' : 'bg-detec-slate-100 text-detec-ui-muted'
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
            <p className="text-sm text-detec-ui-muted mt-1">{policy.description}</p>
          )}
          {isInactiveBaseline && (
            <p className="text-xs text-amber-700 mt-1.5">
              This baseline rule is disabled. Your enforcement posture may be reduced.
            </p>
          )}
        </div>

        {canManage && (
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={onEdit}
              className="rounded px-2 py-1 text-xs text-detec-ui-muted hover:bg-detec-slate-100 hover:text-detec-ui-text transition-colors"
            >
              Edit
            </button>
            <button
              onClick={onToggleActive}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                policy.is_active
                  ? 'text-amber-600 hover:bg-amber-50'
                  : 'text-emerald-600 hover:bg-emerald-50'
              }`}
            >
              {policy.is_active ? 'Disable' : 'Enable'}
            </button>
            {!policy.is_baseline && (
              <button
                onClick={onDelete}
                className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50 transition-colors"
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
    <div className="mt-3 pt-3 border-t border-detec-ui-border">
      {conditionEntries.length > 0 && (
        <div className="mb-2">
          <div className="text-xs text-detec-ui-muted uppercase tracking-wider font-medium mb-1">Conditions</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
            {conditionEntries.map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-1.5 text-xs">
                <span className="text-detec-ui-muted font-mono">{k}:</span>
                <span className="text-detec-ui-text font-mono truncate">
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {rationale && (
        <p className="text-xs text-detec-ui-muted italic mt-1">{rationale}</p>
      )}
      {hasExtra && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mt-1">
          {Object.entries(rest).map(([k, v]) => (
            <div key={k} className="flex items-baseline gap-1.5 text-xs">
              <span className="text-detec-ui-muted font-mono">{k}:</span>
              <span className="text-detec-ui-text font-mono truncate">
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-detec-lg border border-detec-ui-border bg-detec-ui-surface p-4 sm:p-6 shadow-detec-card max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-ui-text mb-4">
          {isEdit ? 'Edit Policy' : 'Create Policy'}
          {isBaseline && (
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-detec-ui-accent/15 text-detec-ui-accent border border-detec-ui-accent/30 align-middle">
              Baseline
            </span>
          )}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Rule ID</label>
              <input
                type="text"
                value={ruleId}
                onChange={(e) => setRuleId(e.target.value)}
                placeholder="e.g. CUSTOM-001"
                disabled={isBaseline}
                className={`w-full rounded-detec border border-detec-ui-border bg-white px-3 py-2 text-sm text-detec-ui-text font-mono focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent focus:outline-none shadow-detec-sm ${
                  isBaseline ? 'opacity-50 cursor-not-allowed' : ''
                }`}
                required
              />
              {isBaseline && (
                <p className="text-xs text-detec-ui-muted mt-1">Rule ID is locked on baseline policies</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-detec-ui-muted mb-1">Version</label>
              <input
                type="text"
                value={ruleVersion}
                onChange={(e) => setRuleVersion(e.target.value)}
                placeholder="0.4.0"
                className="w-full rounded-detec border border-detec-ui-border bg-white px-3 py-2 text-sm text-detec-ui-text font-mono focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent focus:outline-none shadow-detec-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this policy does"
              className="w-full rounded-detec border border-detec-ui-border bg-white px-3 py-2 text-sm text-detec-ui-text focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent focus:outline-none shadow-detec-sm"
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
              <div className="h-5 w-9 rounded-full bg-detec-slate-200 border border-detec-ui-border after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:shadow after:transition-all peer-checked:bg-detec-ui-accent peer-checked:after:translate-x-full peer-checked:after:bg-white" />
            </label>
            <span className="text-sm text-detec-ui-text">
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-ui-muted mb-1">
              Parameters
              <span className="text-detec-ui-muted font-normal ml-1">(JSON)</span>
            </label>
            <textarea
              value={paramsText}
              onChange={(e) => { setParamsText(e.target.value); setParamsError(null); }}
              onBlur={() => validateParams(paramsText)}
              rows={8}
              spellCheck={false}
              className={`w-full rounded-detec border bg-white px-3 py-2 text-sm text-detec-ui-text font-mono focus:outline-none resize-y shadow-detec-sm ${
                paramsError
                  ? 'border-red-500 focus:ring-2 focus:ring-red-500/30'
                  : 'border-detec-ui-border focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent'
              }`}
            />
            {paramsError && (
              <p className="mt-1 text-xs text-red-600">Invalid JSON: {paramsError}</p>
            )}
          </div>

          {formError && (
            <div className="rounded-detec border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-detec border border-detec-ui-border px-4 py-2 text-sm text-detec-ui-muted hover:bg-detec-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-detec bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onCancel}>
      <div
        className="w-full max-w-sm rounded-detec-lg border border-detec-ui-border bg-detec-ui-surface p-4 sm:p-6 shadow-detec-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-detec-ui-text mb-2">{title}</h3>
        <p className="text-sm text-detec-ui-muted mb-5">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-detec border border-detec-ui-border px-4 py-2 text-sm text-detec-ui-muted hover:bg-detec-slate-100"
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
