import { useMemo } from 'react';

function getStatus(counts, endpoints = []) {
  const blocked = counts?.block ?? 0;
  const approvalRequired = counts?.approval_required ?? 0;
  const hasAlerts = blocked > 0 || approvalRequired > 0;
  const nonConformant = endpoints.filter((ep) => ep.management_state !== 'managed').length;
  const hasActivePosture = endpoints.some((ep) => ep.enforcement_posture === 'active' || ep.enforcement_posture === 'audit');
  const total = endpoints.length || 1;
  const postureLabel = endpoints.length === 0
    ? 'No endpoints'
    : endpoints.every((ep) => ep.enforcement_posture === 'passive')
      ? 'Passive'
      : hasActivePosture
        ? 'Mixed'
        : 'Passive';

  if (hasAlerts && blocked > 0) {
    return {
      state: 'critical',
      title: 'Attention Required',
      summary: `${blocked} blocked • ${approvalRequired} approval required`,
      className: 'border-detec-enforce-block/40 bg-detec-enforce-block/5 text-detec-enforce-block',
      pulse: false,
    };
  }
  if (hasAlerts || nonConformant > 0) {
    return {
      state: 'attention',
      title: 'Attention Required',
      summary: nonConformant > 0
        ? `${nonConformant} endpoint${nonConformant !== 1 ? 's' : ''} nonconformant • Enforcement: ${postureLabel}`
        : `${approvalRequired} approval required • Enforcement: ${postureLabel}`,
      className: 'border-detec-amber-500/40 bg-detec-slate-800/50 text-detec-amber-500',
      pulse: true,
    };
  }
  return {
    state: 'healthy',
    title: 'System Status: Healthy',
    summary: `${total} endpoint${total !== 1 ? 's' : ''} connected • Enforcement: ${postureLabel} • No policy violations`,
    className: 'border-detec-teal-500/30 bg-detec-slate-800/50 text-detec-teal-500',
    pulse: false,
  };
}

export default function SystemStatusBanner({ counts = {}, endpoints = [] }) {
  const status = useMemo(() => getStatus(counts, endpoints), [counts, endpoints]);

  return (
    <div
      className={`rounded-lg border px-4 py-2.5 text-sm ${status.className} ${status.pulse ? 'detec-status-pulse' : ''}`}
      role="status"
      aria-live="polite"
    >
      <span className="font-semibold">{status.title}</span>
      <span className="text-detec-slate-400 ml-2">{status.summary}</span>
    </div>
  );
}
