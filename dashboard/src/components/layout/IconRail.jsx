import { useState, useEffect } from 'react';
import DetecLogo from '../branding/DetecLogo';
import { fetchMyTenants, switchTenant } from '../../lib/api';
import { storeTokens } from '../../lib/auth';
import useAuth from '../../hooks/useAuth';

const NAV_ITEMS = [
  { id: 'overview',    label: 'Overview',    icon: OverviewIcon,    path: '/' },
  { id: 'detections',  label: 'Detections',  icon: DetectionsIcon,  path: '/detections' },
  { id: 'policies',    label: 'Policies',    icon: PoliciesIcon,    path: '/policies' },
  { id: 'approvals',   label: 'Approvals',   icon: ApprovalsIcon,   path: '/approvals' },
  { id: 'endpoints',   label: 'Endpoints',   icon: EndpointsIcon,   path: '/endpoints' },
  { id: 'behaviors',   label: 'Behaviors',   icon: BehaviorsIcon,   path: '/behaviors' },
  { id: 'audit',       label: 'Audit',       icon: AuditIcon,       path: '/audit' },
];

const BOTTOM_ITEMS = [
  { id: 'admin', label: 'Admin', icon: AdminIcon, path: '/admin' },
];

export default function IconRail({
  activePage,
  onNavigate,
  alertCount = 0,
  isOpen = false,
  onClose,
}) {
  const { user, refresh } = useAuth();
  const [tenants, setTenants] = useState([]);
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [hovered, setHovered] = useState(false);

  const isOwnerOrAdmin = user?.role === 'owner' || user?.role === 'admin';

  useEffect(() => {
    fetchMyTenants().then(setTenants).catch(() => {});
  }, []);

  const handleNav = (item) => {
    if (item.path === '/') {
      onNavigate('');
    } else {
      onNavigate(item.path.slice(1));
    }
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
  const expanded = hovered || isOpen;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => { setHovered(false); setOrgMenuOpen(false); }}
        className={`
          fixed left-0 top-0 bottom-0 flex flex-col z-50
          bg-detec-ground border-r border-detec-edge
          transition-[width] duration-150 ease-out
          lg:z-30
          ${expanded ? 'w-[200px]' : 'w-14'}
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className={`flex items-center gap-2.5 h-12 border-b border-detec-edge px-3 shrink-0 ${expanded ? '' : 'justify-center'}`}>
          <div className="shrink-0">
            <DetecLogo size="sm" markOnly />
          </div>
          {expanded && (
            <span className="text-xs font-bold text-detec-ink-primary tracking-tight whitespace-nowrap overflow-hidden">
              Detec
            </span>
          )}
        </div>

        {/* Primary nav */}
        <nav className="flex-1 py-2 px-1.5 space-y-0.5 overflow-y-auto" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const active = activePage === item.id;
            const showBadge = item.id === 'detections' && alertCount > 0;
            return (
              <button
                key={item.id}
                type="button"
                title={!expanded ? item.label : undefined}
                onClick={() => handleNav(item)}
                aria-current={active ? 'page' : undefined}
                className={`
                  w-full flex items-center gap-2.5 h-9 rounded-detec text-xs font-medium
                  transition-colors duration-100
                  ${expanded ? 'px-2.5' : 'justify-center px-0'}
                  ${active
                    ? 'bg-detec-brand-muted text-detec-brand border-l-2 border-detec-brand'
                    : 'text-detec-ink-secondary hover:text-detec-ink-primary hover:bg-detec-surface border-l-2 border-transparent'
                  }
                `}
              >
                <item.icon active={active} />
                {expanded && (
                  <span className="whitespace-nowrap overflow-hidden">{item.label}</span>
                )}
                {showBadge && (
                  <span className={`w-1.5 h-1.5 rounded-full bg-detec-enforce-block shrink-0 ${expanded ? 'ml-auto' : 'absolute top-1 right-1'}`} />
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="px-1.5 py-2 border-t border-detec-edge space-y-0.5">
          {/* Admin nav (owner/admin only) */}
          {isOwnerOrAdmin && BOTTOM_ITEMS.map((item) => {
            const active = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                title={!expanded ? item.label : undefined}
                onClick={() => handleNav(item)}
                aria-current={active ? 'page' : undefined}
                className={`
                  w-full flex items-center gap-2.5 h-9 rounded-detec text-xs font-medium
                  transition-colors duration-100
                  ${expanded ? 'px-2.5' : 'justify-center px-0'}
                  ${active
                    ? 'bg-detec-brand-muted text-detec-brand border-l-2 border-detec-brand'
                    : 'text-detec-ink-secondary hover:text-detec-ink-primary hover:bg-detec-surface border-l-2 border-transparent'
                  }
                `}
              >
                <item.icon active={active} />
                {expanded && <span className="whitespace-nowrap overflow-hidden">{item.label}</span>}
              </button>
            );
          })}

          {/* Org switcher */}
          {tenants.length > 1 && (
            <div className="relative">
              <button
                type="button"
                title={currentTenant?.name || 'Organization'}
                onClick={() => setOrgMenuOpen(!orgMenuOpen)}
                className={`
                  w-full flex items-center gap-2 h-9 rounded-detec
                  bg-detec-surface border border-detec-edge text-left
                  hover:border-detec-edge-emphasis transition-colors
                  ${expanded ? 'px-2.5' : 'justify-center px-0'}
                `}
              >
                <span className="w-5 h-5 rounded-detec bg-detec-brand-muted text-detec-brand flex items-center justify-center text-[10px] font-bold shrink-0">
                  {(currentTenant?.name || 'O')[0].toUpperCase()}
                </span>
                {expanded && (
                  <>
                    <span className="text-xs font-medium text-detec-ink-primary truncate flex-1">
                      {currentTenant?.name || 'Organization'}
                    </span>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`text-detec-ink-tertiary shrink-0 transition-transform ${orgMenuOpen ? 'rotate-180' : ''}`} aria-hidden>
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </>
                )}
              </button>
              {orgMenuOpen && expanded && (
                <div className="absolute left-0 right-0 bottom-full mb-1 bg-detec-raised border border-detec-edge rounded-detec-md z-50 overflow-hidden">
                  {otherTenants.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleSwitchTenant(t.id)}
                      disabled={switching}
                      className="w-full flex items-center gap-2 px-2.5 py-2 text-left hover:bg-detec-surface transition-colors disabled:opacity-50"
                    >
                      <span className="w-4 h-4 rounded-detec bg-detec-raised text-detec-ink-primary flex items-center justify-center text-[9px] font-bold shrink-0">
                        {t.name[0].toUpperCase()}
                      </span>
                      <span className="text-xs text-detec-ink-primary truncate">{t.name}</span>
                      <span className="ml-auto text-[10px] text-detec-ink-tertiary">{t.role}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

/* ── Icons (18x18, strokeWidth 1.8) ── */

function OverviewIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function DetectionsIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function PoliciesIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function ApprovalsIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <polyline points="9 11 12 14 22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function EndpointsIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

function BehaviorsIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function AuditIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function AdminIcon({ active }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`shrink-0 ${active ? 'text-detec-brand' : ''}`}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
