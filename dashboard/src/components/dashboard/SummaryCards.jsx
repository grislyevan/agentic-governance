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

export default function SummaryCards({ counts }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {CARDS.map((card) => (
        <div
          key={card.key}
          className={`rounded-xl border px-5 py-4 flex items-center justify-between ${card.color}`}
        >
          <div className="flex items-center gap-3">
            <card.icon />
            <span className={`text-sm font-semibold ${card.text}`}>{card.label}</span>
          </div>
          <span className={`text-2xl font-bold ${card.text}`}>
            {counts[card.key] ?? 0}
          </span>
        </div>
      ))}
    </div>
  );
}

function BlockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
    </svg>
  );
}

function ApprovalIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function WarnIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function DetectIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
