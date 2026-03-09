import { getApiConfig } from '../../lib/api';

export default function EndpointContextBar({ endpointCount, endpoints, endpointStatuses = [] }) {
  const multipleEndpoints = endpoints?.length > 1;
  const firstEp = endpoints?.[0];

  const hostname = multipleEndpoints ? 'Multiple' : (firstEp?.hostname || '—');
  const os = multipleEndpoints ? 'Various' : (firstEp?.os_info || '—');
  const posture = multipleEndpoints ? null : (firstEp?.posture || 'unmanaged');

  const lastSeen = firstEp?.last_seen_at
    ? timeSince(new Date(firstEp.last_seen_at))
    : '—';

  const config = getApiConfig();
  const apiKeyDisplay = config.apiKey
    ? `${config.apiKey.slice(0, 4)}${'*'.repeat(4)}`
    : 'Not configured';

  const statusCounts = computeStatusCounts(endpointStatuses, endpoints);

  return (
    <div className="flex items-center gap-4 text-sm text-detec-slate-400 flex-wrap">
      <span className="flex items-center gap-1.5">
        <span className="text-detec-slate-200 font-semibold">{endpointCount}</span>
        Endpoint{endpointCount !== 1 ? 's' : ''} Connected
        <span className="w-1.5 h-1.5 rounded-full bg-detec-teal-500 ml-0.5" />
      </span>

      <Sep />

      <span className="flex items-center gap-1.5">
        Hostname:
        <span className="text-detec-slate-300">{hostname}</span>
      </span>

      <Sep />

      <span className="flex items-center gap-1.5">
        <span className="text-detec-slate-300">{os}</span>
      </span>

      <Sep />

      {posture && (
        <>
          <span className={`font-mono text-xs px-2 py-0.5 rounded ${posture === 'managed' ? 'bg-detec-teal-500/15 text-detec-teal-500' : 'bg-detec-amber-500/15 text-detec-amber-500'}`}>
            {posture === 'managed' ? 'Conformant' : 'Nonconformant'}
          </span>
          <Sep />
        </>
      )}

      <span className="flex items-center gap-1.5">
        Last Scan:
        <span className="text-detec-primary-400">{lastSeen}</span>
      </span>

      <Sep />

      <span className="flex items-center gap-1.5 font-mono text-xs">
        API Key:
        <span className={config.apiKey ? 'text-detec-slate-500' : 'text-detec-enforce-warn'}>
          {apiKeyDisplay}
        </span>
      </span>

      <span className="ml-auto flex items-center gap-1" title={`${statusCounts.active} active, ${statusCounts.stale} stale, ${statusCounts.ungoverned} ungoverned`}>
        {statusBars(statusCounts).map((h, i) => (
          <span
            key={i}
            className={`w-1 rounded-sm ${h.color}`}
            style={{ height: h.height }}
          />
        ))}
      </span>
    </div>
  );
}

function computeStatusCounts(statuses, endpoints) {
  const counts = { active: 0, stale: 0, ungoverned: 0 };
  const source = statuses?.length ? statuses : endpoints || [];
  for (const ep of source) {
    const s = ep.status || 'active';
    if (s === 'active') counts.active++;
    else if (s === 'stale') counts.stale++;
    else counts.ungoverned++;
  }
  return counts;
}

function statusBars({ active, stale, ungoverned }) {
  const total = active + stale + ungoverned || 1;
  const activeRatio = active / total;
  if (activeRatio > 0.8) return [
    { height: 12, color: 'bg-detec-teal-500' },
    { height: 10, color: 'bg-detec-teal-500' },
    { height: 8, color: 'bg-detec-teal-500' },
    { height: 6, color: 'bg-detec-teal-500' },
    { height: 4, color: 'bg-detec-teal-500' },
  ];
  if (activeRatio > 0.5) return [
    { height: 12, color: 'bg-detec-amber-500' },
    { height: 10, color: 'bg-detec-amber-500' },
    { height: 8, color: 'bg-detec-amber-500' },
    { height: 6, color: 'bg-detec-slate-600' },
    { height: 4, color: 'bg-detec-slate-600' },
  ];
  return [
    { height: 12, color: 'bg-detec-enforce-block' },
    { height: 10, color: 'bg-detec-enforce-block' },
    { height: 8, color: 'bg-detec-slate-600' },
    { height: 6, color: 'bg-detec-slate-600' },
    { height: 4, color: 'bg-detec-slate-600' },
  ];
}

function Sep() {
  return <span className="text-detec-slate-700 select-none" aria-hidden="true">·</span>;
}

function timeSince(date) {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min${minutes > 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr${hours > 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}
