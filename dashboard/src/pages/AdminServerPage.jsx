import { useState, useRef, useEffect } from 'react';
import useAuth from '../hooks/useAuth';
import {
  fetchServerSettings,
  updateServerSettings,
  fetchMyApiKeyStatus,
  rotateMyApiKey,
} from '../lib/api';

export default function AdminServerPage() {
  const { user } = useAuth();
  const canView = user?.role === 'owner' || user?.role === 'admin';

  if (!canView) {
    return (
      <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 text-sm text-detec-ink-secondary">
        You do not have access to server settings.
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6 w-full">
      <ServerGatewaySection />
      <ProgrammaticApiKeySection />
    </div>
  );
}

function ServerGatewaySection() {
  const { user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const savedTimer = useRef(null);

  const [gatewayEnabled, setGatewayEnabled] = useState(true);
  const [gatewayHost, setGatewayHost] = useState('0.0.0.0');
  const [gatewayPort, setGatewayPort] = useState('8001');

  useEffect(() => {
    fetchServerSettings()
      .then((data) => {
        setSettings(data);
        setGatewayEnabled(data.gateway_enabled);
        setGatewayHost(data.gateway_host);
        setGatewayPort(String(data.gateway_port));
      })
      .catch(() => setSettings({}))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => {
      if (savedTimer.current) clearTimeout(savedTimer.current);
    };
  }, []);

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const updated = await updateServerSettings({
        gateway_enabled: gatewayEnabled,
        gateway_host: gatewayHost.trim() || undefined,
        gateway_port: gatewayPort.trim() ? parseInt(gatewayPort, 10) : undefined,
      });
      setSettings(updated);
      setGatewayEnabled(updated.gateway_enabled);
      setGatewayHost(updated.gateway_host);
      setGatewayPort(String(updated.gateway_port));
      setSaved(true);
      if (savedTimer.current) clearTimeout(savedTimer.current);
      savedTimer.current = setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5">
        <p className="text-xs text-detec-ink-secondary">Loading server settings...</p>
      </div>
    );
  }

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
        TCP gateway
      </h2>
      <p className="text-xs text-detec-ink-secondary">
        New agent packages default to <strong>HTTP</strong> so they work when only API port 8000 is exposed.
        Choose <strong>auto</strong> or <strong>TCP</strong> in Deploy Agent when gateway port 8001 is reachable.
        Gateway host and port apply for TCP (auto or tcp).
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
        <label className="flex items-center gap-2 sm:col-span-3">
          <input
            type="checkbox"
            checked={gatewayEnabled}
            onChange={(e) => setGatewayEnabled(e.target.checked)}
            className="rounded border-detec-ui-border bg-detec-surface text-detec-brand focus:ring-detec-brand"
          />
          <span className="text-sm text-detec-ink-primary">Gateway enabled</span>
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">
            Host
          </span>
          <input
            type="text"
            value={gatewayHost}
            onChange={(e) => setGatewayHost(e.target.value)}
            placeholder="0.0.0.0"
            className="w-full bg-detec-void border border-detec-ui-border rounded-detec-md px-3 py-2 text-sm text-detec-ink-primary font-mono placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/50 transition-colors"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">
            Port
          </span>
          <input
            type="number"
            min="1"
            max="65535"
            value={gatewayPort}
            onChange={(e) => setGatewayPort(e.target.value)}
            className="w-full bg-detec-void border border-detec-ui-border rounded-detec-md px-3 py-2 text-sm text-detec-ink-primary font-mono placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/50 transition-colors"
          />
        </label>
      </div>

      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {user?.role === 'owner' && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-detec-brand hover:bg-detec-brand text-white text-sm font-medium rounded-detec-md transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          {saved && (
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-detec-teal-500 detec-toast-enter">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" className="detec-checkmark" />
              </svg>
              Saved. Gateway restarted if enabled.
            </span>
          )}
        </div>
      )}
      {user?.role === 'admin' && (
        <p className="text-xs text-detec-ink-secondary">Only owners can change gateway settings.</p>
      )}
    </div>
  );
}

function ProgrammaticApiKeySection() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newKey, setNewKey] = useState(null);
  const [rotating, setRotating] = useState(false);

  const load = () => {
    setLoading(true);
    fetchMyApiKeyStatus()
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleRotate = async () => {
    if (!window.confirm('Rotate your API key? The old key stops working immediately. Copy the new key once; it will not be shown again.')) return;
    setRotating(true);
    setError(null);
    setNewKey(null);
    try {
      const data = await rotateMyApiKey();
      setNewKey(data.api_key);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setRotating(false);
    }
  };

  return (
    <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
        Programmatic API access
      </h2>
      <p className="text-xs text-detec-ink-secondary">
        Use this key as the <code className="text-detec-ink-primary">X-Api-Key</code> header for scripts and
        automation. Endpoint agents use the tenant agent key from Deploy Agent, not this key. Session
        login uses cookies and does not need this key.
      </p>
      {loading && <p className="text-xs text-detec-ink-secondary">Loading...</p>}
      {error && (
        <div className="rounded-detec-md border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}
      {!loading && status && (
        <>
          <div className="text-sm text-detec-ink-primary">
            <span className="text-detec-ink-secondary">Key prefix: </span>
            <span className="font-mono">{status.prefix_display || 'Not set'}</span>
          </div>
          <button
            type="button"
            onClick={handleRotate}
            disabled={rotating}
            className="px-4 py-2 bg-detec-slate-200 hover:bg-detec-slate-300 text-detec-ink-primary text-sm font-medium rounded-detec-md transition-colors disabled:opacity-50"
          >
            {rotating ? 'Rotating…' : 'Regenerate API key'}
          </button>
        </>
      )}
      {newKey && (
        <div className="rounded-detec-md border border-detec-teal-500/40 bg-detec-teal-500/10 p-4 space-y-2">
          <p className="text-sm font-medium text-detec-teal-600">Copy this key now. It will not be shown again.</p>
          <code className="block text-xs break-all font-mono bg-detec-void p-2 rounded border border-detec-ui-border">
            {newKey}
          </code>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard.writeText(newKey);
            }}
            className="text-sm text-detec-brand font-medium"
          >
            Copy to clipboard
          </button>
        </div>
      )}
    </div>
  );
}
