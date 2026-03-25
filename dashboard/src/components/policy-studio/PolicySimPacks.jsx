/**
 * PolicySimPacks — policy simulation pack profile cards + preview/apply flow.
 *
 * Apply flow:
 *   1. POST /api/enforcement/tenant-posture  { enforcement_posture, auto_enforce_threshold }
 *   2. PATCH /api/policies/:id  { is_active, parameters }  for each rule override in the pack
 *      (matched by rule_id against the current policies list fetched from GET /api/policies)
 *
 * No dedicated bulk-update or preset endpoint maps exactly to the sim-pack schema,
 * so we match policy records by rule_id and PATCH each one individually.
 */

import { useState, useCallback } from 'react';
import { fetchPolicies, updatePolicy, updateTenantPosture } from '../../lib/api';

// ── Pack definitions (mirrors playbook/policy-simulation-packs/*.json) ───────

const PACKS = [
  {
    id: 'visibility-only',
    name: 'Visibility Only',
    subtitle: 'Passive / All detect',
    phase: 'Days 1–14',
    phaseDesc: 'Initial baseline capture',
    description:
      'No enforcement actions fire. All detections are logged for review, giving you full ' +
      'visibility with zero operational impact from false positives.',
    tradeoff:
      'Use this phase to establish baseline event volume, identify FP-prone processes, and ' +
      'populate the allow-list before escalating posture. The cost is zero protection during this window.',
    requiresBaseline: false,
    posture: 'passive',
    overrides: [
      { rule_id: 'ENFORCE-001', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-002', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-003', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-004', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-D01', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-D02', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-D03', is_active: true, parameters: { override_decision: 'detect' } },
    ],
    // Human-readable summary of what each rule becomes
    ruleTable: [
      { rule_id: 'ENFORCE-001', label: 'Low confidence', value: 'detect' },
      { rule_id: 'ENFORCE-002', label: 'Medium confidence', value: 'detect' },
      { rule_id: 'ENFORCE-003', label: 'High confidence', value: 'detect' },
      { rule_id: 'ENFORCE-004', label: 'Class D tools', value: 'detect' },
      { rule_id: 'ENFORCE-D01', label: 'Drift D01', value: 'detect' },
      { rule_id: 'ENFORCE-D02', label: 'Drift D02', value: 'detect' },
      { rule_id: 'ENFORCE-D03', label: 'Drift D03', value: 'detect' },
    ],
  },
  {
    id: 'warn-heavy',
    name: 'Warn Heavy',
    subtitle: 'Audit / Medium+High warn',
    phase: 'Days 14–30',
    phaseDesc: 'Post-baseline tuning',
    description:
      'Analyst notifications fire on Medium and High confidence detections. Under audit posture, ' +
      'enforcement decisions are logged but not applied, so tool activity is not interrupted.',
    tradeoff:
      'The FP cost is alert noise — analysts will triage warn decisions that turn out to be benign. ' +
      'Calibrate allow-list entries before escalating further.',
    requiresBaseline: true,
    posture: 'audit',
    overrides: [
      { rule_id: 'ENFORCE-001', is_active: true, parameters: { override_decision: 'detect', conditions: { confidence_band: ['Low'] } } },
      { rule_id: 'ENFORCE-002', is_active: true, parameters: { override_decision: 'warn',   conditions: { confidence_band: ['Medium'] } } },
      { rule_id: 'ENFORCE-003', is_active: true, parameters: { override_decision: 'warn',   conditions: { confidence_band: ['High'] } } },
      { rule_id: 'ENFORCE-004', is_active: true, parameters: { override_decision: 'approval_required', conditions: { tool_classes: ['D'] } } },
      { rule_id: 'ENFORCE-D01', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-D02', is_active: true, parameters: { override_decision: 'detect' } },
      { rule_id: 'ENFORCE-D03', is_active: true, parameters: { override_decision: 'detect' } },
    ],
    ruleTable: [
      { rule_id: 'ENFORCE-001', label: 'Low confidence', value: 'detect' },
      { rule_id: 'ENFORCE-002', label: 'Medium confidence', value: 'warn' },
      { rule_id: 'ENFORCE-003', label: 'High confidence', value: 'warn' },
      { rule_id: 'ENFORCE-004', label: 'Class D tools', value: 'approval_required' },
      { rule_id: 'ENFORCE-D01', label: 'Drift D01', value: 'detect' },
      { rule_id: 'ENFORCE-D02', label: 'Drift D02', value: 'detect' },
      { rule_id: 'ENFORCE-D03', label: 'Drift D03', value: 'detect' },
    ],
  },
  {
    id: 'approval-required-high-risk',
    name: 'Approval Required — High Risk',
    subtitle: 'Audit / High approval_required, Class D block',
    phase: 'Post-pilot',
    phaseDesc: 'Sustained production use',
    description:
      'High-confidence detections hold tool activity pending analyst review. Class D block rules ' +
      'only take effect if posture is switched to active.',
    tradeoff:
      'This profile has the highest analyst workload and the strongest protection. A false positive ' +
      'at High confidence interrupts legitimate tool use until resolved. Appropriate only after the FP rate is confirmed low.',
    requiresBaseline: true,
    posture: 'audit',
    overrides: [
      { rule_id: 'ENFORCE-001', is_active: true, parameters: { override_decision: 'detect',            conditions: { confidence_band: ['Low'] } } },
      { rule_id: 'ENFORCE-002', is_active: true, parameters: { override_decision: 'warn',              conditions: { confidence_band: ['Medium'] } } },
      { rule_id: 'ENFORCE-003', is_active: true, parameters: { override_decision: 'approval_required', conditions: { confidence_band: ['High'] } } },
      { rule_id: 'ENFORCE-004', is_active: true, parameters: { override_decision: 'block',             conditions: { tool_classes: ['D'], sensitivity_tiers: ['Tier0', 'Tier1'] } } },
      { rule_id: 'ENFORCE-D01', is_active: true, parameters: { override_decision: 'warn' } },
      { rule_id: 'ENFORCE-D02', is_active: true, parameters: { override_decision: 'warn' } },
      { rule_id: 'ENFORCE-D03', is_active: true, parameters: { override_decision: 'warn' } },
    ],
    ruleTable: [
      { rule_id: 'ENFORCE-001', label: 'Low confidence', value: 'detect' },
      { rule_id: 'ENFORCE-002', label: 'Medium confidence', value: 'warn' },
      { rule_id: 'ENFORCE-003', label: 'High confidence', value: 'approval_required' },
      { rule_id: 'ENFORCE-004', label: 'Class D tools', value: 'block' },
      { rule_id: 'ENFORCE-D01', label: 'Drift D01', value: 'warn' },
      { rule_id: 'ENFORCE-D02', label: 'Drift D02', value: 'warn' },
      { rule_id: 'ENFORCE-D03', label: 'Drift D03', value: 'warn' },
    ],
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

const DECISION_CLASSES = {
  detect:            'bg-blue-100 text-blue-700 border-blue-200',
  warn:              'bg-yellow-100 text-yellow-700 border-yellow-200',
  approval_required: 'bg-amber-100 text-amber-700 border-amber-200',
  block:             'bg-red-100 text-red-700 border-red-200',
};

function DecisionBadge({ value }) {
  const cls = DECISION_CLASSES[value] || 'bg-detec-slate-100 text-detec-ui-muted border-detec-ui-border';
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border ${cls}`}>
      {value}
    </span>
  );
}

function PhaseBadge({ phase }) {
  return (
    <span className="inline-flex items-center rounded-full bg-detec-ui-accent/10 px-2.5 py-0.5 text-xs font-medium text-detec-ui-accent">
      {phase}
    </span>
  );
}

/** Extract the current override_decision for a rule from its parameters field. */
function extractCurrentDecision(policy) {
  if (!policy) return '—';
  const p = policy.parameters || {};
  return p.override_decision || p.decision_state || (policy.is_active ? 'active' : 'inactive') || '—';
}

// ── Preview modal ─────────────────────────────────────────────────────────────

function PreviewModal({ pack, currentPolicies, onClose, onApply, applying, applyError }) {
  const [acknowledged, setAcknowledged] = useState(false);

  // Build diff rows
  const diffRows = pack.ruleTable.map((row) => {
    const current = currentPolicies.find((p) => p.rule_id === row.rule_id);
    const currentDecision = extractCurrentDecision(current);
    const changed = currentDecision !== row.value;
    return { ...row, currentDecision, changed };
  });

  const hasChanges = diffRows.some((r) => r.changed);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-xl border border-detec-ui-border bg-detec-ui-page p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-detec-ui-text">{pack.name}</h2>
            <p className="text-sm text-detec-ui-muted mt-0.5">{pack.subtitle}</p>
          </div>
          <button
            onClick={onClose}
            className="text-detec-ui-muted hover:text-detec-ui-text transition-colors shrink-0"
            aria-label="Close preview"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Posture row */}
        <div className="flex items-center gap-3 rounded-lg border border-detec-ui-border/60 bg-detec-slate-100/40 px-4 py-3 text-sm">
          <span className="font-medium text-detec-ui-text">Posture:</span>
          <span className="text-detec-ui-muted">current</span>
          <span className="text-detec-ui-muted">→</span>
          <span className="font-semibold text-detec-ui-text capitalize">{pack.posture}</span>
        </div>

        {/* Diff table */}
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-detec-ui-muted mb-2">Rule overrides</h3>
          <div className="rounded-lg border border-detec-ui-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-detec-ui-border bg-detec-slate-100/40">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-detec-ui-muted">Rule</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-detec-ui-muted">Current</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-detec-ui-muted">Pack sets</th>
                </tr>
              </thead>
              <tbody>
                {diffRows.map((row, i) => (
                  <tr
                    key={row.rule_id}
                    className={`border-b border-detec-ui-border/50 last:border-0 ${
                      row.changed ? 'bg-amber-50' : ''
                    } ${i % 2 === 0 && !row.changed ? 'bg-detec-ui-surface/20' : ''}`}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs text-detec-ui-text">{row.rule_id}</span>
                      <span className="ml-2 text-xs text-detec-ui-muted">{row.label}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <DecisionBadge value={row.currentDecision} />
                    </td>
                    <td className="px-4 py-2.5">
                      <DecisionBadge value={row.value} />
                      {row.changed && (
                        <span className="ml-2 text-xs text-amber-600 font-medium">changed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!hasChanges && (
            <p className="text-xs text-detec-ui-muted mt-2">No rule changes — current policies already match this pack.</p>
          )}
        </div>

        {/* Baseline warning banner */}
        {pack.requiresBaseline && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 space-y-2">
            <p className="text-sm font-semibold text-amber-800">
              You must run visibility-only for at least 7 days before applying this profile.
            </p>
            <p className="text-sm text-amber-700">
              Skipping this phase means your FP rate is unknown. Applying warn or enforcement postures
              without a baseline will generate analyst workload for detections you have not yet assessed.
            </p>
            <label className="flex items-start gap-2 cursor-pointer mt-2">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="mt-0.5 shrink-0 accent-amber-600"
              />
              <span className="text-sm text-amber-800 font-medium">
                I understand — apply anyway
              </span>
            </label>
          </div>
        )}

        {applyError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {applyError}
          </div>
        )}

        {/* Footer actions */}
        <div className="flex justify-end gap-3 pt-1">
          <button
            onClick={onClose}
            className="text-sm px-4 py-1.5 rounded-lg text-detec-ui-muted hover:text-detec-ui-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onApply}
            disabled={applying || (pack.requiresBaseline && !acknowledged)}
            className={`text-sm px-5 py-1.5 rounded-lg font-medium transition-colors ${
              applying || (pack.requiresBaseline && !acknowledged)
                ? 'bg-detec-slate-200 text-detec-ui-muted cursor-not-allowed'
                : 'bg-detec-ui-accent text-white hover:bg-detec-ui-accentHover cursor-pointer'
            }`}
          >
            {applying ? 'Applying…' : `Apply ${pack.name}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Confirmation dialog (visibility-only only) ────────────────────────────────

function ConfirmDialog({ pack, onConfirm, onCancel, applying, applyError }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md rounded-xl border border-detec-ui-border bg-detec-ui-page p-6 shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-detec-ui-text">Apply {pack.name}?</h2>
        <p className="text-sm text-detec-ui-muted">
          All rules will be set to <strong>detect</strong>. Posture will be set to{' '}
          <strong>passive</strong>. No enforcement actions will fire.
        </p>

        {applyError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {applyError}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-lg text-detec-ui-muted hover:text-detec-ui-text transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={applying}
            onClick={onConfirm}
            className={`text-sm px-5 py-1.5 rounded-lg font-medium transition-colors ${
              applying
                ? 'bg-detec-slate-200 text-detec-ui-muted cursor-not-allowed'
                : 'bg-detec-ui-accent text-white hover:bg-detec-ui-accentHover cursor-pointer'
            }`}
          >
            {applying ? 'Applying…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Pack card ─────────────────────────────────────────────────────────────────

function PackCard({ pack, onPreview }) {
  return (
    <div className="rounded-xl border border-detec-ui-border bg-detec-ui-surface/60 p-5 flex flex-col gap-3 shadow-detec-sm hover:shadow-detec-card transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-detec-ui-text">{pack.name}</h3>
          <p className="text-xs text-detec-ui-muted mt-0.5">{pack.subtitle}</p>
        </div>
        <PhaseBadge phase={pack.phase} />
      </div>

      <p className="text-xs text-detec-ui-muted leading-relaxed">{pack.phaseDesc}</p>
      <p className="text-xs text-detec-ui-text leading-relaxed">{pack.description}</p>
      <p className="text-xs text-detec-ui-muted leading-relaxed italic">{pack.tradeoff}</p>

      <div className="mt-auto pt-1">
        <button
          type="button"
          onClick={() => onPreview(pack)}
          className="rounded-detec border border-detec-ui-border px-4 py-1.5 text-xs font-medium text-detec-ui-text hover:bg-detec-slate-100 transition-colors"
        >
          Preview
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PolicySimPacks({ onApplied }) {
  const [previewPack, setPreviewPack] = useState(null);
  const [confirmPack, setConfirmPack] = useState(null);
  const [currentPolicies, setCurrentPolicies] = useState([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const openPreview = useCallback(async (pack) => {
    setApplyError(null);
    setSuccessMsg(null);
    setLoadingPolicies(true);
    try {
      // Fetch all policies to build the diff (up to 200; enough for baseline set)
      const data = await fetchPolicies({}, { page: 1, pageSize: 200 });
      setCurrentPolicies(data.items || []);
    } catch {
      setCurrentPolicies([]);
    } finally {
      setLoadingPolicies(false);
    }

    if (pack.id === 'visibility-only') {
      // Straight to confirmation dialog
      setConfirmPack(pack);
    } else {
      setPreviewPack(pack);
    }
  }, []);

  /** Apply a pack: set tenant posture, then PATCH each matching policy rule. */
  const applyPack = useCallback(async (pack) => {
    setApplying(true);
    setApplyError(null);
    try {
      // 1. Set tenant-wide posture
      await updateTenantPosture({ enforcement_posture: pack.posture });

      // 2. PATCH each policy override matched by rule_id
      const policiesData = currentPolicies.length
        ? currentPolicies
        : (await fetchPolicies({}, { page: 1, pageSize: 200 })).items || [];

      const patchPromises = pack.overrides.map((override) => {
        const existing = policiesData.find((p) => p.rule_id === override.rule_id);
        if (!existing) return Promise.resolve(null); // rule not found — skip
        return updatePolicy(existing.id, {
          is_active: override.is_active,
          parameters: { ...existing.parameters, ...override.parameters },
        });
      });

      await Promise.all(patchPromises);

      setSuccessMsg(`${pack.name} profile applied.`);
      setPreviewPack(null);
      setConfirmPack(null);
      onApplied?.();
    } catch (err) {
      setApplyError(err.message || 'Failed to apply profile. Check your permissions.');
    } finally {
      setApplying(false);
    }
  }, [currentPolicies, onApplied]);

  return (
    <>
      {/* Success toast */}
      {successMsg && (
        <div className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-2.5 text-sm text-teal-700 flex items-center justify-between">
          <span>{successMsg}</span>
          <button
            onClick={() => setSuccessMsg(null)}
            className="ml-4 text-teal-500 hover:text-teal-700 transition-colors text-xs"
            aria-label="Dismiss"
          >
            Dismiss
          </button>
        </div>
      )}

      {loadingPolicies && (
        <div className="text-xs text-detec-ui-muted py-1">Loading policy data…</div>
      )}

      {/* Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {PACKS.map((pack) => (
          <PackCard key={pack.id} pack={pack} onPreview={openPreview} />
        ))}
      </div>

      {/* Preview modal (warn-heavy / approval-required-high-risk) */}
      {previewPack && (
        <PreviewModal
          pack={previewPack}
          currentPolicies={currentPolicies}
          onClose={() => { setPreviewPack(null); setApplyError(null); }}
          onApply={() => applyPack(previewPack)}
          applying={applying}
          applyError={applyError}
        />
      )}

      {/* Confirm dialog (visibility-only) */}
      {confirmPack && (
        <ConfirmDialog
          pack={confirmPack}
          onConfirm={() => applyPack(confirmPack)}
          onCancel={() => { setConfirmPack(null); setApplyError(null); }}
          applying={applying}
          applyError={applyError}
        />
      )}
    </>
  );
}
