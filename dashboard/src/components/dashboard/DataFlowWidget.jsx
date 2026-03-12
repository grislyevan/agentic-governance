import { useState, useEffect } from 'react';
import { fetchDataFlowSummary } from '../../lib/api';

export default function DataFlowWidget() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    setLoading(true);
    fetchDataFlowSummary(days)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) {
    return (
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/30 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-detec-slate-200">AI Data Flow</h3>
        </div>
        <div className="text-xs text-detec-slate-500 animate-pulse">Loading data flow...</div>
      </div>
    );
  }

  if (!data || data.total_connections === 0) {
    return (
      <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-detec-slate-200">AI Data Flow</h3>
          <DaySelector days={days} onChange={setDays} />
        </div>
        <div className="text-xs text-detec-slate-500">No LLM API traffic detected in the last {days} days.</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/30 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-detec-slate-200">AI Data Flow</h3>
        <DaySelector days={days} onChange={setDays} />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatCard label="Destinations" value={data.unique_destinations} />
        <StatCard label="Cloud" value={data.cloud_llm_connections} color="text-blue-400" />
        <StatCard label="Local" value={data.local_llm_connections} color="text-emerald-400" />
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

function StatCard({ label, value, color = 'text-detec-slate-100' }) {
  return (
    <div className="rounded-lg bg-detec-slate-900/50 border border-detec-slate-700/30 px-3 py-2 text-center">
      <div className={`text-lg font-bold tabular-nums ${color}`}>{value}</div>
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
