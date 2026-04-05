import { useNavigate, useLocation, Outlet } from 'react-router-dom';

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const onUsers = location.pathname === '/admin' || location.pathname === '/admin/';
  const onSso = location.pathname === '/admin/sso';
  const onServer = location.pathname === '/admin/server';

  const tabCls = (on) =>
    `px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${on ? 'bg-detec-brand text-white' : 'text-detec-ink-secondary hover:text-detec-ink-primary'}`;

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-detec-ink-primary">Admin</h1>
        <nav className="flex flex-wrap rounded-detec border border-detec-ui-border bg-detec-surface p-0.5 gap-0.5" aria-label="Admin sections">
          <button
            type="button"
            onClick={() => navigate('/admin')}
            aria-current={onUsers ? 'page' : undefined}
            className={tabCls(onUsers)}
          >
            Users
          </button>
          <button
            type="button"
            onClick={() => navigate('/admin/server')}
            aria-current={onServer ? 'page' : undefined}
            className={tabCls(onServer)}
          >
            Server
          </button>
          <button
            type="button"
            onClick={() => navigate('/admin/sso')}
            aria-current={onSso ? 'page' : undefined}
            className={tabCls(onSso)}
          >
            SSO
          </button>
        </nav>
      </div>
      <Outlet />
    </div>
  );
}
