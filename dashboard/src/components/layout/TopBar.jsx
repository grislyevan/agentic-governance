import { useState, useRef, useEffect } from 'react';
import useAuth from '../../hooks/useAuth';

const TOP_NAV = [
  { id: 'endpoints', label: 'Endpoints' },
  { id: 'events', label: 'Events' },
  { id: 'policies', label: 'Policies' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'admin', label: 'Admin' },
];

export default function TopBar({ activePage, onNavigate, onSearch, onRefresh, alertCount = 0, onMenuClick }) {
  const { user, logout } = useAuth();
  const [searchValue, setSearchValue] = useState('');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchValue(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch?.(val);
    }, 250);
  };

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || 'User';
  const initials = [user?.first_name?.[0], user?.last_name?.[0]].filter(Boolean).join('').toUpperCase() || '?';

  return (
    <header className="h-14 bg-detec-slate-900 border-b border-detec-slate-700/50 flex items-center justify-between gap-3 px-4 sm:px-6 shrink-0 min-h-[44px]">
      <div className="flex items-center gap-2 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2.5 -ml-1 text-detec-slate-400 hover:text-detec-slate-200 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
          aria-label="Open menu"
        >
          <MenuIcon />
        </button>
        <nav className="hidden lg:flex items-center gap-1" aria-label="Section navigation">
          {TOP_NAV.map((item) => {
          const active = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              aria-current={active ? 'page' : undefined}
              className={`
                flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors
                ${active
                  ? 'text-detec-slate-100'
                  : 'text-detec-slate-400 hover:text-detec-slate-200'
                }
              `}
            >
              {item.label}
            </button>
          );
        })}
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0 max-w-md lg:mx-6">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-detec-slate-500" />
          <input
            type="text"
            value={searchValue}
            onChange={handleSearchChange}
            placeholder="Search tools..."
            aria-label="Search tools"
            className="w-full bg-detec-slate-800 border border-detec-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-detec-slate-200 placeholder:text-detec-slate-500 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          />
        </div>
        <button
          onClick={onRefresh}
          className="p-2.5 sm:p-1.5 bg-detec-slate-800 border border-detec-slate-700 rounded-lg text-detec-slate-400 hover:text-detec-slate-200 transition-colors min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center shrink-0"
          title="Refresh data"
        >
          <RefreshIcon />
        </button>
      </div>

      <div className="flex items-center gap-1 sm:gap-3 shrink-0">
        <button
          className="relative p-2.5 sm:p-1.5 text-detec-slate-400 hover:text-detec-slate-200 transition-colors min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center"
          aria-label={`Notifications${alertCount > 0 ? `, ${alertCount} alerts` : ''}`}
          title={alertCount > 0 ? `${alertCount} alerts requiring attention` : 'No alerts'}
        >
          <BellIcon />
          {alertCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-detec-enforce-block text-[10px] font-bold text-white flex items-center justify-center">
              {alertCount > 99 ? '99+' : alertCount}
            </span>
          )}
        </button>

        <div className="relative" ref={userMenuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-expanded={showUserMenu}
            aria-haspopup="true"
            aria-label="User menu"
            className="flex items-center gap-2 sm:gap-2.5 pl-2 sm:pl-3 border-l border-detec-slate-700/50 cursor-pointer hover:opacity-80 transition-opacity min-h-[44px] py-1"
          >
            <div className="w-8 h-8 rounded-full bg-detec-primary-500/20 border border-detec-primary-500/30 flex items-center justify-center text-xs font-semibold text-detec-primary-400 shrink-0">
              {initials}
            </div>
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-detec-slate-200 leading-tight truncate max-w-[120px] lg:max-w-none">
                {displayName}
              </div>
              <div className="text-xs text-detec-slate-500 leading-tight">
                {user?.role || 'analyst'}
              </div>
            </div>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 top-full mt-2 w-48 bg-detec-slate-800 border border-detec-slate-700 rounded-lg shadow-lg py-1 z-50">
              <div className="px-3 py-2 border-b border-detec-slate-700/50">
                <div className="text-xs text-detec-slate-500 truncate">{user?.email}</div>
              </div>
              <button
                onClick={() => { onNavigate('settings'); setShowUserMenu(false); }}
                className="w-full text-left px-3 py-2 text-sm text-detec-slate-300 hover:bg-detec-slate-700/50 transition-colors"
              >
                Settings
              </button>
              <button
                onClick={logout}
                className="w-full text-left px-3 py-2 text-sm text-detec-enforce-block hover:bg-detec-slate-700/50 transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function SearchIcon({ className = '' }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}
