import { useState, useEffect } from 'react';
import DetecLogo from '../branding/DetecLogo';
import { fetchBillingStatus, fetchMyTenants, switchTenant } from '../../lib/api';
import { storeTokens } from '../../lib/auth';
import useAuth from '../../hooks/useAuth';

const NAV_ITEMS = [
  { id: 'endpoints', label: 'AI Inventory', icon: EndpointsIcon },
  { id: 'sessions', label: 'Sessions', icon: SessionsIcon },
  { id: 'events', label: 'Events', icon: EventsIcon },
  { id: 'policies', label: 'Policies', icon: PoliciesIcon },
  { id: 'audit', label: 'Audit Log', icon: AuditIcon },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
];

const TIER_BADGE_COLORS = {
  free: 'bg-detec-slate-200 text-detec-ui-muted',
  pro: 'bg-detec-ui-accent/15 text-detec-ui-accent',
  enterprise: 'bg-amber-500/20 text-amber-600',
};

export default function Sidebar({
  activePage,
  onNavigate,
  alertCount = 0,
  isOpen = false,
  onClose,
  collapsed = false,
  onToggleCollapse,
}) {
  const { user, refresh } = useAuth();
  const [planTier, setPlanTier] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    fetchBillingStatus()
      .then((data) => setPlanTier(data.tier))
      .catch(() => {});
    fetchMyTenants()
      .then(setTenants)
      .catch(() => {});
  }, []);

  const handleNav = (page) => {
    onNavigate(page);
    onClose?.();
  };

  const handleSwitchTenant = async (tenantId) => {
    if (switching || tenantId === user?.tenant_id) return;
    setSwitching(true);
    try {
      const data = await switchTenant(tenantId);
      storeTokens(data);
      setOrgMenuOpen(false);
      await refresh();
      window.location.reload();
    } catch {
      // silent
    } finally {
      setSwitching(false);
    }
  };

  const currentTenant = tenants.find((t) => t.id === user?.tenant_id);
  const otherTenants = tenants.filter((t) => t.id !== user?.tenant_id);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`
          fixed left-0 top-0 bottom-0 w-60 flex flex-col z-50
          bg-white/95 backdrop-blur-md border-r border-slate-200/80 shadow-[4px_0_24px_-8px_rgba(15,23,42,0.08)]
          transform transition-all duration-200 ease-out
          lg:translate-x-0 lg:z-30
          ${collapsed ? 'lg:w-16' : 'lg:w-60'}
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        aria-expanded={collapsed ? undefined : true}
      >
      <div
        className={`flex items-center gap-3 border-b border-slate-100 bg-gradient-to-b from-white to-slate-50/50 px-5 py-5 lg:px-3 ${
          collapsed ? 'lg:justify-center lg:px-2' : ''
        }`}
      >
        <div className="rounded-xl bg-slate-50 p-1.5 ring-1 ring-slate-200/80 shadow-sm shrink-0">
          <DetecLogo size="sm" markOnly />
        </div>
        <span
          className={`text-sm font-bold font-display text-slate-800 leading-tight tracking-tight ${
            collapsed ? 'lg:sr-only' : ''
          }`}
        >
          Agentic AI<br /><span className="text-slate-500 font-semibold text-[13px]">Governance</span>
        </span>
      </div>

      {tenants.length > 0 && (
        <div className={`px-3 pt-3 pb-1 relative ${collapsed ? 'lg:px-1.5' : ''}`}>
          <button
            type="button"
            title={currentTenant?.name || user?.tenant_name || 'Organization'}
            onClick={() => setOrgMenuOpen(!orgMenuOpen)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-detec bg-white border border-detec-ui-border text-left hover:border-detec-slate-300 transition-colors shadow-detec-sm ${
              collapsed ? 'lg:justify-center lg:px-1' : ''
            }`}
          >
            <span className="w-6 h-6 rounded bg-detec-ui-accent/15 text-detec-ui-accent flex items-center justify-center text-xs font-bold flex-shrink-0">
              {(currentTenant?.name || 'O')[0].toUpperCase()}
            </span>
            <span
              className={`text-xs font-medium text-detec-ui-text truncate flex-1 ${
                collapsed ? 'lg:sr-only' : ''
              }`}
            >
              {currentTenant?.name || user?.tenant_name || 'Organization'}
            </span>
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={`text-detec-ui-muted transition-transform shrink-0 ${orgMenuOpen ? 'rotate-180' : ''} ${collapsed ? 'lg:hidden' : ''}`}
              aria-hidden
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          {orgMenuOpen && (
            <div className="absolute left-3 right-3 top-full mt-1 bg-detec-ui-surface border border-detec-ui-border rounded-detec shadow-detec-card z-50 overflow-hidden">
              {otherTenants.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleSwitchTenant(t.id)}
                  disabled={switching}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-detec-slate-100 transition-colors disabled:opacity-50"
                >
                  <span className="w-5 h-5 rounded bg-detec-slate-200 text-detec-ui-text flex items-center justify-center text-[10px] font-bold flex-shrink-0">
                    {t.name[0].toUpperCase()}
                  </span>
                  <span className="text-xs text-detec-ui-text truncate">{t.name}</span>
                  <span className="ml-auto text-[10px] text-detec-ui-muted">{t.role}</span>
                </button>
              ))}
              <button
                onClick={() => { handleNav('org'); setOrgMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2.5 text-left border-t border-detec-ui-border hover:bg-detec-slate-100 transition-colors"
              >
                <span className="w-5 h-5 rounded border border-dashed border-detec-ui-border flex items-center justify-center text-detec-ui-muted">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                </span>
                <span className="text-xs text-detec-ui-muted">Manage organizations</span>
              </button>
            </div>
          )}
        </div>
      )}

      <nav className={`flex-1 py-3 px-3 space-y-0.5 overflow-y-auto ${collapsed ? 'lg:px-1.5' : ''}`} aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const active = activePage === item.id;
          const showBadge = item.id === 'events' && alertCount > 0;
          return (
            <button
              key={item.id}
              type="button"
              title={item.label}
              onClick={() => handleNav(item.id)}
              aria-current={active ? 'page' : undefined}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold min-h-[44px]
                transition-all duration-150 text-left
                ${collapsed ? 'lg:justify-center lg:px-2' : ''}
                ${active
                  ? 'bg-gradient-to-r from-blue-50 to-sky-50/80 text-detec-ui-accent shadow-sm ring-1 ring-blue-100/80'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                }
              `}
            >
              <item.icon active={active} />
              <span className={collapsed ? 'lg:sr-only' : ''}>{item.label}</span>
              {showBadge && (
                <span
                  className={`w-1.5 h-1.5 rounded-full bg-detec-ui-accent shrink-0 ml-auto ${collapsed ? 'lg:hidden' : ''}`}
                />
              )}
            </button>
          );
        })}
      </nav>

      <div className={`px-3 py-2 border-t border-detec-ui-border space-y-0.5 ${collapsed ? 'lg:px-1.5' : ''}`}>
        <button
          type="button"
          onClick={() => onToggleCollapse?.()}
          className="hidden lg:flex w-full items-center justify-center gap-2 px-2 py-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 text-xs font-medium"
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={collapsed ? '' : 'rotate-180'}>
            <polyline points="15 18 9 12 15 6" />
          </svg>
          <span className={collapsed ? 'sr-only' : ''}>{collapsed ? '' : 'Collapse'}</span>
        </button>
      </div>

      <div className={`px-3 py-3 border-t border-detec-ui-border space-y-0.5 ${collapsed ? 'lg:px-1.5' : ''}`}>
        <button
          type="button"
          title="Billing"
          onClick={() => handleNav('billing')}
          aria-current={activePage === 'billing' ? 'page' : undefined}
          className={`
            w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold min-h-[44px]
            transition-all duration-150 text-left
            ${collapsed ? 'lg:justify-center lg:px-2' : ''}
            ${activePage === 'billing'
              ? 'bg-gradient-to-r from-blue-50 to-sky-50/80 text-detec-ui-accent shadow-sm ring-1 ring-blue-100/80'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
            }
          `}
        >
          <BillingIcon active={activePage === 'billing'} />
          <span className={collapsed ? 'lg:sr-only' : ''}>Billing</span>
          {planTier && !collapsed && (
            <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium uppercase lg:inline ${TIER_BADGE_COLORS[planTier] || TIER_BADGE_COLORS.free}`}>
              {planTier}
            </span>
          )}
        </button>
        <button
          type="button"
          title="Admin"
          onClick={() => handleNav('admin')}
          aria-current={activePage === 'admin' ? 'page' : undefined}
          className={`
            w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold min-h-[44px]
            transition-all duration-150 text-left
            ${collapsed ? 'lg:justify-center lg:px-2' : ''}
            ${activePage === 'admin'
              ? 'bg-gradient-to-r from-blue-50 to-sky-50/80 text-detec-ui-accent shadow-sm ring-1 ring-blue-100/80'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
            }
          `}
        >
          <AdminIcon active={activePage === 'admin'} />
          <span className={collapsed ? 'lg:sr-only' : ''}>Admin</span>
        </button>
      </div>
    </aside>
    </>
  );
}

function EndpointsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

function SessionsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function EventsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <path d="M12 8v4l3 3" />
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

function PoliciesIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function AuditIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
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
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function BillingIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  );
}

function SettingsIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={active ? 'text-detec-ui-accent' : 'text-detec-ui-muted'}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
