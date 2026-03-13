import { useState, useEffect } from 'react';
import { fetchDataFlowSummary } from '../../lib/api';

const FRESH_SEC = 120;
const STALE_SEC = 900;

function freshnessDotClass(secs) {
  if (secs == null) return 'bg-detec-slate-500';
  if (secs < FRESH_SEC) return 'bg-detec-teal-500';
  if (secs < STALE_SEC) return 'bg-detec-amber-500';
  return 'bg-detec-enforce-block';
}

function DataFlowFreshness({ lastUpdated }) {
  const [secs, setSecs] = useState(null);
  const [label, setLabel] = useState('Live');
  useEffect(() => {
    if (!lastUpdated) return;
    const update = () => {
      const s = Math.round((Date.now() - lastUpdated) / 1000);
      setSecs(s);
      setLabel(s < 5 ? 'Live' : s < 60 ? `Last update ${s}s ago` : `Last update ${Math.floor(s / 60)}m ago`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [lastUpdated]);
  if (!lastUpdated) return null;
  return (
    <span className="flex items-center gap-1.5 text-xs text-detec-slate-500">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${freshnessDotClass(secs)}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export default function DataFlowWidget() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchDataFlowSummary(days)
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => { setLoading(false); setLastUpdated(Date.now()); });
  }, [days]);

  if (loading) {
    return (
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/30 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-detec-slate-200">AI Data Flow</h3>
        </div>
        <div className="text-xs text-detec-slate-500 animate-pulse" aria-label="Loading data flow">Loading...</div>
      </div>
    );
  }

  if (!data || data.total_connections === 0) {
    return (
      <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-detec-slate-200" title="LLM API destinations and request counts seen from your endpoints.">AI Data Flow</h3>
            <DataFlowFreshness lastUpdated={lastUpdated} />
          </div>
          <DaySelector days={days} onChange={setDays} />
        </div>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <StatCard label="Total requests" value={0} />
          <StatCard label="Unique tools" value={0} />
          <StatCard label="Top destination" value="-" />
        </div>
        <p className="text-xs text-detec-slate-500">No LLM API traffic detected in the last {days} days.</p>
        <p className="text-xs text-detec-slate-600 mt-1.5">When your endpoints talk to LLM APIs, destinations and request counts will show here.</p>
      </div>
    );
  }

  const topDestination = data.destinations?.length > 0 ? data.destinations[0].provider : '-';
  const uniqueTools = data.unique_tools ?? (() => {
    const set = new Set();
    (data.destinations || []).forEach((d) => (d.tools || []).forEach((t) => set.add(t)));
    return set.size;
  })();

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/30 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-detec-slate-200" title="LLM API destinations and request counts seen from your endpoints.">AI Data Flow</h3>
          <DataFlowFreshness lastUpdated={lastUpdated} />
        </div>
        <DaySelector days={days} onChange={setDays} />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatCard label="Total requests" value={data.total_connections} />
        <StatCard label="Unique tools" value={uniqueTools} />
        <StatCard label="Top destination" value={topDestination} className="text-xs truncate max-w-full" valueTitle={topDestination} />
      </div>

      {data.destinations.length > 0 && (
        <div className="space-y-1.5">
          {data.destinations.slice(0, 8).map((d) => (
            <div key={d.host} className="flex items-center gap-2 text-xs">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                d.host.startsWith('localhost') || d.host.startsWith('127.')
                  ? 'bg-emerald-400'
                  : 'bg-blue-400'
              }`} />
              <span className="text-detec-slate-300 truncate flex-1 font-medium">{d.provider}</span>
              <span className="text-detec-slate-500 tabular-nums">{d.request_count} req</span>
              <span className="text-detec-slate-600 tabular-nums">{d.endpoint_count} ep</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color = 'text-detec-slate-100', className = '', valueTitle }) {
  return (
    <div className="rounded-lg bg-detec-slate-900/50 border border-detec-slate-700/30 px-3 py-2 text-center min-w-0">
      <div className={`text-lg font-bold tabular-nums ${color} ${className}`} title={valueTitle}>
        {value}
      </div>
      <div className="text-[10px] text-detec-slate-500 uppercase tracking-wider">{label}</div>
    </div>
  );
}

function DaySelector({ days, onChange }) {
  return (
    <select
      value={days}
      onChange={(e) => onChange(Number(e.target.value))}
      className="text-[10px] bg-detec-slate-900/50 border border-detec-slate-700/30 text-detec-slate-400 rounded px-1.5 py-0.5"
    >
      <option value={1}>24h</option>
      <option value={7}>7d</option>
      <option value={30}>30d</option>
    </select>
  );
}
