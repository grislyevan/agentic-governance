export default function EventsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-detec-slate-100">Events</h1>
      <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
        <div className="text-3xl mb-3 opacity-40">
          <PulseIcon />
        </div>
        <div className="text-detec-slate-400 text-sm font-medium mb-1">
          No events yet
        </div>
        <div className="text-detec-slate-600 text-sm max-w-sm mx-auto">
          Detection, policy, and enforcement events will appear here as endpoints report in.
          Connect an agent to get started.
        </div>
      </div>
    </div>
  );
}

function PulseIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
