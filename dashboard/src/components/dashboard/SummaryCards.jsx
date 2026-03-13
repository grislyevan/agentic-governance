const CARDS = [
  {
    key: 'block',
    label: 'Blocked',
    color: 'bg-detec-enforce-block/15 border-detec-enforce-block/30',
    text: 'text-detec-enforce-block',
    icon: BlockIcon,
  },
  {
    key: 'approval_required',
    label: 'Approval Required',
    color: 'bg-detec-enforce-approval/15 border-detec-enforce-approval/30',
    text: 'text-detec-enforce-approval',
    icon: ApprovalIcon,
  },
  {
    key: 'warn',
    label: 'Warned',
    color: 'bg-detec-enforce-warn/15 border-detec-enforce-warn/30',
    text: 'text-detec-enforce-warn',
    icon: WarnIcon,
  },
  {
    key: 'detect',
    label: 'Detected',
    color: 'bg-detec-enforce-detect/15 border-detec-enforce-detect/30',
    text: 'text-detec-enforce-detect',
    icon: DetectIcon,
  },
];

const MUTED_CARD = 'bg-detec-slate-800/50 border-detec-slate-700';
const MUTED_TEXT = 'text-detec-slate-500';

export default function SummaryCards({ counts }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {CARDS.map((card) => {
        const value = counts[card.key] ?? 0;
        const isZero = value === 0;
        const cardColor = isZero ? MUTED_CARD : card.color;
        const labelClass = isZero ? `text-sm font-semibold ${MUTED_TEXT}` : `text-sm font-semibold ${card.text}`;
        const valueClass = isZero ? `text-2xl font-bold ${MUTED_TEXT}` : `text-3xl font-bold ${card.text}`;
        const hoverClass = isZero ? '' : 'transition-colors duration-150 hover:border-opacity-50 motion-reduce:transition-none';
        return (
          <div
            key={card.key}
            className={`rounded-xl border px-5 py-4 flex items-center justify-between ${cardColor} ${hoverClass}`}
          >
            <div className="flex items-center gap-3">
              <card.icon muted={isZero} />
              <span className={labelClass}>{card.label}</span>
            </div>
            <span className={valueClass}>{value}</span>
          </div>
        );
      })}
    </div>
  );
}

function BlockIcon({ muted }) {
  const stroke = muted ? '#64748b' : '#ef4444';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </svg>
  );
}

function ApprovalIcon({ muted }) {
  const stroke = muted ? '#64748b' : '#f97316';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function WarnIcon({ muted }) {
  const stroke = muted ? '#64748b' : '#fbbf24';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function DetectIcon({ muted }) {
  const stroke = muted ? '#64748b' : '#14b8a6';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
