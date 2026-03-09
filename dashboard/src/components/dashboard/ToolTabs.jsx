const TABS = [
  { id: 'all', label: 'All Tools' },
  { id: 'block', label: 'Blocked' },
  { id: 'approval_required', label: 'Approval' },
  { id: 'warn', label: 'Warned' },
];

export default function ToolTabs({ activeTab, onTabChange, counts, totalTools, onNavigate }) {
  const tabCounts = {
    all: totalTools,
    block: counts.block,
    approval_required: counts.approval_required,
    warn: counts.warn,
  };

  return (
    <div className="flex items-center justify-between border-b border-detec-slate-700/50">
      <div className="flex items-center gap-0.5" role="tablist" aria-label="Tool filter tabs">
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          const count = tabCounts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={active}
              onClick={() => onTabChange(tab.id)}
              className={`
                flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                ${active
                  ? 'border-detec-primary-500 text-detec-slate-100'
                  : 'border-transparent text-detec-slate-400 hover:text-detec-slate-300'
                }
              `}
            >
              {tab.label}
              <span className={`
                text-xs px-1.5 py-0.5 rounded-full
                ${active
                  ? 'bg-detec-primary-500/20 text-detec-primary-400'
                  : 'bg-detec-slate-800 text-detec-slate-500'
                }
              `}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-4 text-sm">
        <button
          onClick={() => onNavigate?.('events')}
          className="text-detec-slate-400 hover:text-detec-slate-200 transition-colors flex items-center gap-1.5"
        >
          <LogIcon />
          Collector logs
        </button>
        <button
          onClick={() => onNavigate?.('policies')}
          className="text-detec-primary-400 hover:text-detec-primary-300 transition-colors flex items-center gap-1.5"
        >
          <EyeIcon />
          View policies
        </button>
      </div>
    </div>
  );
}

function LogIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
