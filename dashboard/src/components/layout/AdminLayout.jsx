import { useNavigate, useLocation, Outlet } from 'react-router-dom';

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const onPlaybooks = location.pathname === '/playbooks';

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-detec-slate-100">Admin</h1>
        <nav className="flex rounded-lg border border-detec-slate-700/50 bg-detec-slate-800/50 p-0.5" aria-label="Admin sections">
          <button
            onClick={() => navigate('/admin')}
            aria-current={!onPlaybooks ? 'page' : undefined}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${!onPlaybooks ? 'bg-detec-slate-700 text-detec-slate-200' : 'text-detec-slate-400 hover:text-detec-slate-200'}`}
          >
            Users
          </button>
          <button
            onClick={() => navigate('/playbooks')}
            aria-current={onPlaybooks ? 'page' : undefined}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${onPlaybooks ? 'bg-detec-slate-700 text-detec-slate-200' : 'text-detec-slate-400 hover:text-detec-slate-200'}`}
          >
            Playbooks
          </button>
        </nav>
      </div>
      <Outlet />
    </div>
  );
}
