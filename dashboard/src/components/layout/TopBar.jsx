import { useState, useRef, useEffect } from 'react';
import useAuth from '../../hooks/useAuth';
import useTenants from '../../hooks/useTenants';
import { switchTenant } from '../../lib/api';
import { setActiveTenantId } from '../../lib/auth';

const TOP_NAV = [
  { id: 'endpoints', label: 'Endpoints' },
  { id: 'events', label: 'Events' },
  { id: 'policies', label: 'Policies' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'admin', label: 'Admin' },
];

export default function TopBar({ activePage, onNavigate, onSearch, onRefresh, alertCount = 0, onMenuClick }) {
  const { user, logout } = useAuth();
  const { tenants } = useTenants();
  const [searchValue, setSearchValue] = useState('');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showOrgSwitcher, setShowOrgSwitcher] = useState(false);
  const [alertOnApproval, setAlertOnApproval] = useState(true);
  const [emailDigest, setEmailDigest] = useState(false);
  const [switching, setSwitching] = useState(false);
  const userMenuRef = useRef(null);
  const notificationsRef = useRef(null);
  const orgSwitcherRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(e.target)) {
        setShowNotifications(false);
      }
      if (orgSwitcherRef.current && !orgSwitcherRef.current.contains(e.target)) {
        setShowOrgSwitcher(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const activeTenantId = user?.activeTenantId;
  const activeTenant = tenants.find((t) => String(t.id) === String(activeTenantId)) ?? tenants[0] ?? null;

  async function handleSwitchTenant(tenantId) {
    if (switching || String(tenantId) === String(activeTenantId)) {
      setShowOrgSwitcher(false);
      return;
    }
    setSwitching(true);
    try {
      await switchTenant(tenantId);
      setActiveTenantId(tenantId);
    } catch {
      // If switch fails, still update local preference; server will validate
    } finally {
      setSwitching(false);
      setShowOrgSwitcher(false);
      window.location.reload();
    }
  }

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
    <header className="h-14 bg-detec-ui-surface border-b border-detec-ui-border flex items-center justify-between gap-3 px-4 sm:px-6 shrink-0 min-h-[44px] shadow-detec-sm">
      <div className="flex items-center gap-2 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2.5 -ml-1 text-detec-ui-muted hover:text-detec-ui-text rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
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
                  ? 'text-detec-ui-text font-medium'
                  : 'text-detec-ui-muted hover:text-detec-ui-text'
                }
              `}
            >
              {item.label}
            </button>
          );
        })}
        </nav>
      </div>

      {/* Org switcher — desktop only, between nav and search */}
      {tenants.length > 0 && (
        <div className="hidden lg:flex items-center shrink-0 relative" ref={orgSwitcherRef}>
          {tenants.length === 1 ? (
            <span className="px-3 py-1.5 text-sm font-medium text-detec-ui-muted border border-detec-ui-border rounded-detec bg-detec-ui-surface max-w-[160px] truncate" title={activeTenant?.name}>
              {activeTenant?.name ?? ''}
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setShowOrgSwitcher(!showOrgSwitcher)}
                aria-expanded={showOrgSwitcher}
                aria-haspopup="listbox"
                aria-label="Switch organisation"
                disabled={switching}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors border border-detec-ui-border bg-detec-ui-surface text-detec-ui-text hover:bg-detec-slate-100 disabled:opacity-60 max-w-[180px]"
              >
                <BuildingIcon />
                <span className="truncate max-w-[120px]">{activeTenant?.name ?? 'Select org'}</span>
                <ChevronDownIcon />
              </button>
              {showOrgSwitcher && (
                <div
                  role="listbox"
                  aria-label="Select organisation"
                  className="absolute left-0 top-full mt-2 w-56 bg-detec-ui-surface border border-detec-ui-border rounded-detec shadow-detec-card py-1 z-50"
                >
                  <div className="px-3 py-2 border-b border-detec-ui-border">
                    <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Switch organisation</span>
                  </div>
                  {tenants.map((t) => {
                    const isActive = String(t.id) === String(activeTenantId) || (!activeTenantId && t === tenants[0]);
                    return (
                      <button
                        key={t.id}
                        role="option"
                        aria-selected={isActive}
                        type="button"
                        onClick={() => handleSwitchTenant(t.id)}
                        className="w-full text-left px-3 py-2.5 text-sm text-detec-ui-text hover:bg-detec-slate-100 transition-colors flex items-center justify-between gap-2"
                      >
                        <span className="flex flex-col min-w-0">
                          <span className="truncate font-medium">{t.name}</span>
                          {t.role && (
                            <span className="text-xs text-detec-ui-muted capitalize">{t.role}</span>
                          )}
                        </span>
                        {isActive && <CheckIcon />}
                      </button>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0 max-w-md lg:mx-6">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-detec-ui-muted" />
          <input
            type="text"
            value={searchValue}
            onChange={handleSearchChange}
            placeholder="Search tools..."
            aria-label="Search tools"
            className="w-full bg-white border border-detec-ui-border rounded-detec pl-9 pr-3 py-1.5 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/30 focus:border-detec-ui-accent transition-colors shadow-detec-sm"
          />
        </div>
        <button
          onClick={onRefresh}
          className="p-2.5 sm:p-1.5 bg-white border border-detec-ui-border rounded-detec text-detec-ui-muted hover:text-detec-ui-text transition-colors min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center shrink-0 shadow-detec-sm"
          title="Refresh data"
        >
          <RefreshIcon />
        </button>
      </div>

      <div className="flex items-center gap-1 sm:gap-3 shrink-0">
        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            aria-expanded={showNotifications}
            aria-haspopup="true"
            aria-label={`Notifications${alertCount > 0 ? `, ${alertCount} alerts` : ''}`}
            title={alertCount > 0 ? `${alertCount} alerts requiring attention` : 'Notification settings'}
            className="relative p-2.5 sm:p-1.5 text-detec-ui-muted hover:text-detec-ui-text transition-colors min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center"
          >
            <BellIcon />
            {alertCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-detec-enforce-block text-[10px] font-bold text-white flex items-center justify-center">
                {alertCount > 99 ? '99+' : alertCount}
              </span>
            )}
          </button>
          {showNotifications && (
            <div className="absolute right-0 top-full mt-2 w-64 bg-detec-ui-surface border border-detec-ui-border rounded-detec shadow-detec-card py-1 z-50">
              <div className="px-3 py-2 border-b border-detec-ui-border">
                <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Notifications</span>
              </div>
              <label className="flex items-center gap-2 px-3 py-2.5 text-sm text-detec-ui-text hover:bg-detec-slate-100 cursor-pointer">
                <input
                  type="checkbox"
                  checked={alertOnApproval}
                  onChange={(e) => setAlertOnApproval(e.target.checked)}
                  className="rounded border-detec-ui-border bg-white text-detec-ui-accent focus:ring-detec-ui-accent/30"
                />
                <span>Alert me when tools need approval</span>
              </label>
              <label className="flex items-center gap-2 px-3 py-2.5 text-sm text-detec-ui-text hover:bg-detec-slate-100 cursor-pointer">
                <input
                  type="checkbox"
                  checked={emailDigest}
                  onChange={(e) => setEmailDigest(e.target.checked)}
                  className="rounded border-detec-ui-border bg-white text-detec-ui-accent focus:ring-detec-ui-accent/30"
                />
                <span>Email digest</span>
              </label>
              <div className="border-t border-detec-ui-border">
                <button
                  type="button"
                  onClick={() => { onNavigate('events'); setShowNotifications(false); }}
                  className="w-full text-left px-3 py-2 text-sm text-detec-ui-text hover:bg-detec-slate-100 transition-colors"
                >
                  View all events
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="relative" ref={userMenuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-expanded={showUserMenu}
            aria-haspopup="true"
            aria-label="User menu"
            className="flex items-center gap-2 sm:gap-2.5 pl-2 sm:pl-3 border-l border-detec-ui-border cursor-pointer hover:opacity-80 transition-opacity min-h-[44px] py-1"
          >
            <div className="w-8 h-8 rounded-full bg-detec-ui-accent/15 border border-detec-ui-accent/30 flex items-center justify-center text-xs font-semibold text-detec-ui-accent shrink-0">
              {initials}
            </div>
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-detec-ui-text leading-tight truncate max-w-[120px] lg:max-w-none">
                {displayName}
              </div>
              <div className="text-xs text-detec-ui-muted leading-tight">
                {user?.role || 'analyst'}
              </div>
            </div>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 top-full mt-2 w-48 bg-detec-ui-surface border border-detec-ui-border rounded-detec shadow-detec-card py-1 z-50">
              <div className="px-3 py-2 border-b border-detec-ui-border">
                <div className="text-xs text-detec-ui-muted truncate">{user?.email}</div>
              </div>
              <button
                onClick={() => { onNavigate('settings'); setShowUserMenu(false); }}
                className="w-full text-left px-3 py-2 text-sm text-detec-ui-text hover:bg-detec-slate-100 transition-colors"
              >
                Settings
              </button>
              <button
                onClick={logout}
                className="w-full text-left px-3 py-2 text-sm text-detec-enforce-block hover:bg-red-50 transition-colors"
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

function BuildingIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 opacity-60">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 text-detec-ui-accent">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
