export default function AdminPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-detec-slate-100">Admin</h1>
      <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
        <div className="text-3xl mb-3 opacity-40">
          <UsersIcon />
        </div>
        <div className="text-detec-slate-400 text-sm font-medium mb-1">
          Admin panel coming soon
        </div>
        <div className="text-detec-slate-600 text-sm max-w-sm mx-auto">
          Tenant management, user roles, and API key administration.
          For now, manage these via the API directly.
        </div>
      </div>
    </div>
  );
}

function UsersIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}
