import { useState, useEffect, useCallback } from 'react';
import { fetchPolicies } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';

export default function PoliciesPage() {
  const [policies, setPolicies] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPolicies();
      setPolicies(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-detec-slate-100">Policies</h1>
        {loading && <ApertureSpinner size="sm" label="Loading policies" />}
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      {policies.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-20 text-center">
          <div className="mb-3 opacity-40">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="text-detec-slate-400 text-sm font-medium mb-1">No policies configured yet</div>
          <div className="text-detec-slate-600 text-sm max-w-sm mx-auto">
            Policies define how Detec responds to each tool class. Without them, everything stays at Detect.
            Create your first policy via the API.
          </div>
        </div>
      )}

      {policies.length > 0 && (
        <div className="grid gap-3">
          {policies.map((policy) => (
            <div key={policy.id} className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-detec-slate-200 font-mono">{policy.rule_id}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-detec-slate-700 text-detec-slate-400">v{policy.rule_version}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${policy.is_active ? 'bg-detec-teal-500/15 text-detec-teal-500' : 'bg-detec-slate-700 text-detec-slate-500'}`}>
                      {policy.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  {policy.description && (
                    <p className="text-sm text-detec-slate-400">{policy.description}</p>
                  )}
                </div>
              </div>
              {policy.parameters && Object.keys(policy.parameters).length > 0 && (
                <div className="mt-3 pt-3 border-t border-detec-slate-700/50">
                  <div className="text-xs text-detec-slate-500 uppercase tracking-wider font-medium mb-1">Parameters</div>
                  <pre className="text-xs text-detec-slate-400 font-mono bg-detec-slate-900/50 rounded p-2 overflow-x-auto">
                    {JSON.stringify(policy.parameters, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {total > 0 && (
        <div className="text-sm text-detec-slate-500 text-center">
          {total} {total === 1 ? 'policy' : 'policies'} total
        </div>
      )}
    </div>
  );
}
