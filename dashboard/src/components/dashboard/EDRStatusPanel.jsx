import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchEDRStatus, updateEDRConfig, testEDRConnectivity } from '../../lib/api';

const PROVIDER_OPTIONS = [
  { value: '', label: 'Local (no EDR)' },
  { value: 'crowdstrike', label: 'CrowdStrike Falcon' },
  { value: 'sentinelone', label: 'SentinelOne' },
];

export default function EDRStatusPanel({ endpointId, isAdmin = false }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('');
  const testTimer = useRef(null);

  useEffect(() => {
    return () => { if (testTimer.current) clearTimeout(testTimer.current); };
  }, []);

  const loadStatus = useCallback(async () => {
    if (!endpointId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEDRStatus(endpointId);
      setStatus(data);
      setSelectedProvider(data.enforcement_provider || '');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [endpointId]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const handleProviderChange = async (provider) => {
    setSelectedProvider(provider);
    setSaving(true);
    setError(null);
    try {
      await updateEDRConfig(endpointId, {
        enforcement_provider: provider || null,
      });
      await loadStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await testEDRConnectivity(endpointId);
      setTestResult(result);
      if (testTimer.current) clearTimeout(testTimer.current);
      testTimer.current = setTimeout(() => setTestResult(null), 10000);
    } catch (err) {
      setError(err.message);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5">
        <h3 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider mb-3">
          EDR Enforcement
        </h3>
        <p className="text-sm text-detec-slate-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
          EDR Enforcement
        </h3>
        {status?.available && (
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Connected
          </span>
        )}
        {status && !status.available && status.enforcement_provider && (
          <span className="inline-flex items-center gap-1.5 text-xs text-detec-amber-500">
            <span className="h-1.5 w-1.5 rounded-full bg-detec-amber-500" />
            Unreachable
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-xs text-detec-slate-500 uppercase tracking-wider">Provider</span>
          {isAdmin ? (
            <select
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
              disabled={saving}
              className="mt-1 w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 focus:outline-none focus:border-detec-primary-500/50 transition-colors disabled:opacity-50"
            >
              {PROVIDER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          ) : (
            <p className="mt-1 text-detec-slate-200">
              {status?.enforcement_provider
                ? PROVIDER_OPTIONS.find(o => o.value === status.enforcement_provider)?.label || status.enforcement_provider
                : 'Local (no EDR)'}
            </p>
          )}
        </div>

        <div>
          <span className="text-xs text-detec-slate-500 uppercase tracking-wider">EDR Host ID</span>
          <p className="mt-1 font-mono text-xs text-detec-slate-400 break-all">
            {status?.edr_host_id || 'Not resolved'}
          </p>
        </div>
      </div>

      {status?.enforcement_provider && isAdmin && (
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-4 py-2 bg-detec-primary-600 hover:bg-detec-primary-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {testing ? 'Testing...' : 'Test EDR Connection'}
          </button>

          {testResult && (
            <div className="text-xs space-y-0.5">
              <p className={testResult.host_resolved ? 'text-emerald-400' : 'text-red-400'}>
                Host resolution: {testResult.host_resolved ? 'OK' : 'Failed'}
              </p>
              <p className={testResult.rtr_session_ok ? 'text-emerald-400' : 'text-detec-amber-500'}>
                RTR session: {testResult.rtr_session_ok ? 'OK' : 'Unavailable'}
              </p>
            </div>
          )}
        </div>
      )}

      {status?.registered_providers?.length > 0 && (
        <p className="text-xs text-detec-slate-600">
          Registered providers: {status.registered_providers.join(', ')}
        </p>
      )}
    </div>
  );
}
