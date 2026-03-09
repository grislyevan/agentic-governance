import DetecLogo from '../branding/DetecLogo';

const NAV_ITEMS = [
  { id: 'endpoints', label: 'Endpoints', icon: EndpointsIcon },
  { id: 'events', label: 'Events', icon: EventsIcon },
  { id: 'policies', label: 'Policies', icon: PoliciesIcon },
  { id: 'audit', label: 'Audit Log', icon: AuditIcon },
  { id: 'admin', label: 'Admin', icon: AdminIcon },
];

export default function Sidebar({ activePage, onNavigate, alertCount = 0 }) {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-detec-slate-950 border-r border-detec-slate-700/50 flex flex-col z-30">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-detec-slate-700/50">
        <DetecLogo size="sm" markOnly />
        <span className="text-sm font-semibold text-detec-slate-100 leading-tight">
          Agentic AI<br />Governance
        </span>
      </div>

      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const active = activePage === item.id;
          const showBadge = item.id === 'events' && alertCount > 0;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                transition-colors duration-150 text-left
                ${active
                  ? 'bg-detec-primary-500/15 text-detec-primary-400'
                  : 'text-detec-slate-400 hover:text-detec-slate-200 hover:bg-detec-slate-800/60'
                }
              `}
            >
              <item.icon active={active} />
              <span>{item.label}</span>
              {showBadge && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-detec-primary-400" />
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-3 py-3 border-t border-detec-slate-700/50">
        <button
          onClick={() => onNavigate('settings')}
          className={`
            w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
            transition-colors duration-150 text-left
            ${activePage === 'settings'
              ? 'bg-detec-primary-500/15 text-detec-primary-400'
              : 'text-detec-slate-400 hover:text-detec-slate-200 hover:bg-detec-slate-800/60'
            }
          `}
        >
          <SettingsIcon active={activePage === 'settings'} />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

function EndpointsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

function EventsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <path d="M12 8v4l3 3" />
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

function PoliciesIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function AuditIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function AdminIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function SettingsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-primary-400' : 'text-detec-slate-400'}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
