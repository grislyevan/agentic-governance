import { useState, useRef, useEffect, useCallback } from 'react';
import { getApiConfig, setApiConfig, fetchSsoStatus, fetchWebhooks, fetchWebhookTemplates, createWebhook, createWebhookFromTemplate, updateWebhook, deleteWebhook, testWebhook, fetchServerSettings, updateServerSettings, downloadAgent, enrollAgentByEmail, fetchAllowList, addAllowListEntry, deleteAllowListEntry, updateTenantPosture, fetchPostureSummary, fetchDisabledServices, restoreServices } from '../lib/api';
import useAuth from '../hooks/useAuth';

const EVENT_TYPES = [
  'enforcement.block',
  'enforcement.approval_required',
  'enforcement.warn',
  'enforcement.allow',
  'tool.detected',
  'tool.removed',
];

export default function SettingsPage() {
  const config = getApiConfig();
  const { user } = useAuth();
  const [apiUrl, setApiUrl] = useState(config.apiUrl);
  const [apiKey, setApiKey] = useState(config.apiKey);
  const [saved, setSaved] = useState(false);
  const savedTimer = useRef(null);

  const canManageWebhooks = user?.role === 'owner' || user?.role === 'admin';

  useEffect(() => {
    return () => { if (savedTimer.current) clearTimeout(savedTimer.current); };
  }, []);

  const handleSave = () => {
    setApiConfig({ apiUrl, apiKey });
    setSaved(true);
    if (savedTimer.current) clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 min-w-0">
      <h1 className="text-xl sm:text-2xl font-bold text-detec-slate-100">Settings</h1>

      <div className="max-w-2xl space-y-6 w-full">
        <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
            API Connection
          </h2>

          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
              API URL
            </span>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="/api"
              spellCheck={false}
              className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
              API Key
            </span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="X-Api-Key"
              spellCheck={false}
              className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
            />
          </label>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-detec-primary-500 hover:bg-detec-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Save
            </button>
            {saved && (
              <span className="inline-flex items-center gap-1.5 text-sm font-medium text-detec-teal-500 detec-toast-enter">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" className="detec-checkmark" />
                </svg>
                Saved
              </span>
            )}
          </div>
        </div>

        {user?.role === 'owner' && <SsoConfigSection />}

        {canManageWebhooks && <ServerGatewaySection />}

        {canManageWebhooks && <AgentDownloadSection />}

        {canManageWebhooks && <WebhooksSection />}

        {canManageWebhooks && <TenantPostureSection />}

        {canManageWebhooks && <AllowListSection />}

        {canManageWebhooks && <DisabledServicesSection />}
      </div>
    </div>
  );
}


function SsoConfigSection() {
  const [ssoStatus, setSsoStatus] = useState(null);

  useEffect(() => {
    fetchSsoStatus().then((data) => setSsoStatus(data)).catch(() => setSsoStatus({ configured: false }));
  }, []);

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
        SSO Configuration
      </h2>
      <p className="text-xs text-detec-slate-500">
        SSO is configured via environment variables on the server. Configure OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, and OIDC_REDIRECT_URI to enable sign-in with your identity provider.
      </p>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-detec-slate-400">Status:</span>
          {ssoStatus === null ? (
            <span className="text-xs text-detec-slate-500">Loading...</span>
          ) : ssoStatus.configured ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Configured
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-detec-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-detec-slate-600" />Not configured
            </span>
          )}
        </div>
        {ssoStatus?.configured && ssoStatus.issuer && (
          <div className="text-xs text-detec-slate-500">
            OIDC issuer: <code className="break-all">{ssoStatus.issuer}</code>
          </div>
        )}
      </div>
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
    return () => { if (savedTimer.current) clearTimeout(savedTimer.current); };
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
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5">
        <p className="text-xs text-detec-slate-500">Loading server settings...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
        TCP Gateway
      </h2>
      <p className="text-xs text-detec-slate-500">
        Agents can connect via HTTP (default) or a persistent TCP connection. Configure the gateway host and port here; agent downloads use these values when TCP is selected.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
        <label className="flex items-center gap-2 sm:col-span-3">
          <input
            type="checkbox"
            checked={gatewayEnabled}
            onChange={(e) => setGatewayEnabled(e.target.checked)}
            className="rounded border-detec-slate-600 bg-detec-slate-800 text-detec-primary-500 focus:ring-detec-primary-500"
          />
          <span className="text-sm text-detec-slate-300">Gateway enabled</span>
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
            Host
          </span>
          <input
            type="text"
            value={gatewayHost}
            onChange={(e) => setGatewayHost(e.target.value)}
            placeholder="0.0.0.0"
            className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
            Port
          </span>
          <input
            type="number"
            min="1"
            max="65535"
            value={gatewayPort}
            onChange={(e) => setGatewayPort(e.target.value)}
            className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          />
        </label>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {user?.role === 'owner' && (
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-detec-primary-500 hover:bg-detec-primary-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
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
        <p className="text-xs text-detec-slate-500">Only owners can change gateway settings.</p>
      )}
    </div>
  );
}

const PLATFORMS = [
  { value: 'macos', label: 'macOS' },
  { value: 'windows', label: 'Windows' },
  { value: 'linux', label: 'Linux' },
];

function AgentDownloadSection() {
  const [platform, setPlatform] = useState('macos');
  const [interval, setInterval_] = useState('300');
  const [protocol, setProtocol] = useState('http');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const successTimer = useRef(null);

  const [enrollEmail, setEnrollEmail] = useState('');
  const [enrolling, setEnrolling] = useState(false);
  const [enrollSuccess, setEnrollSuccess] = useState(null);
  const enrollTimer = useRef(null);

  useEffect(() => {
    return () => {
      if (successTimer.current) clearTimeout(successTimer.current);
      if (enrollTimer.current) clearTimeout(enrollTimer.current);
    };
  }, []);

  const handleDownload = async () => {
    setError(null);
    setSuccess(false);
    setDownloading(true);
    try {
      await downloadAgent({
        platform,
        interval: interval || undefined,
        protocol: protocol || undefined,
      });
      setSuccess(true);
      if (successTimer.current) clearTimeout(successTimer.current);
      successTimer.current = setTimeout(() => setSuccess(false), 4000);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  const handleEnroll = async () => {
    if (!enrollEmail.trim()) return;
    setError(null);
    setEnrollSuccess(null);
    setEnrolling(true);
    try {
      await enrollAgentByEmail({
        email: enrollEmail.trim(),
        platform,
        interval: parseInt(interval, 10) || 300,
        protocol,
      });
      setEnrollSuccess(enrollEmail.trim());
      setEnrollEmail('');
      if (enrollTimer.current) clearTimeout(enrollTimer.current);
      enrollTimer.current = setTimeout(() => setEnrollSuccess(null), 6000);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnrolling(false);
    }
  };

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
        Deploy Agent
      </h2>
      <p className="text-xs text-detec-slate-500">
        Download a pre-configured agent package or email a download link to a user.
        The server URL and credentials are embedded automatically, so the agent connects
        with zero manual setup after install.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
            Platform
          </span>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </label>

        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
            Interval (sec)
          </span>
          <input
            type="number"
            min="30"
            max="86400"
            value={interval}
            onChange={(e) => setInterval_(e.target.value)}
            className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          />
        </label>

        <label className="block space-y-1.5">
          <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
            Protocol
          </span>
          <select
            value={protocol}
            onChange={(e) => setProtocol(e.target.value)}
            className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          >
            <option value="http">HTTP</option>
            <option value="tcp">TCP (binary protocol)</option>
          </select>
        </label>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="px-4 py-2 bg-detec-primary-500 hover:bg-detec-primary-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {downloading ? 'Downloading\u2026' : platform === 'windows' ? 'Download Installer' : 'Download Agent'}
        </button>
        {success && (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-detec-teal-500 detec-toast-enter">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" className="detec-checkmark" />
            </svg>
            Download started
          </span>
        )}
      </div>

      <div className="border-t border-detec-slate-700/30 pt-4 mt-2 space-y-3">
        <h3 className="text-xs font-semibold text-detec-slate-400 uppercase tracking-wider">
          Email to User
        </h3>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="email"
            value={enrollEmail}
            onChange={(e) => setEnrollEmail(e.target.value)}
            placeholder="user@company.com"
            spellCheck={false}
            className="flex-1 min-w-0 bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-3 sm:py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors min-h-[44px] sm:min-h-0"
          />
          <button
            onClick={handleEnroll}
            disabled={enrolling || !enrollEmail.trim()}
            className="px-4 py-3 sm:py-2 bg-detec-primary-600 hover:bg-detec-primary-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap min-h-[44px] sm:min-h-0"
          >
            {enrolling ? 'Sending...' : 'Send Download Link'}
          </button>
        </div>
        {enrollSuccess && (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-detec-teal-500 detec-toast-enter">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" className="detec-checkmark" />
            </svg>
            Download link sent to {enrollSuccess} (expires in 72 hours)
          </span>
        )}
      </div>
    </div>
  );
}


function WebhooksSection() {
  const [webhooks, setWebhooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);

  const loadWebhooks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWebhooks();
      setWebhooks(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadWebhooks(); }, [loadWebhooks]);

  const handleDelete = async (id) => {
    if (!confirm('Delete this webhook?')) return;
    try {
      await deleteWebhook(id);
      loadWebhooks();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleTest = async (id) => {
    try {
      const result = await testWebhook(id);
      if (result.success) {
        setError(null);
      } else {
        setError('Test delivery failed. Check the webhook URL.');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggle = async (webhook) => {
    try {
      await updateWebhook(webhook.id, { is_active: !webhook.is_active });
      loadWebhooks();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
          Webhooks
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTemplateModal(true)}
            className="rounded-lg border border-detec-primary-500/50 px-3 py-1.5 text-xs font-medium text-detec-primary-400 hover:bg-detec-primary-500/10 transition-colors"
          >
            Create from template
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="rounded-lg bg-detec-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-detec-primary-500 transition-colors"
          >
            Add webhook
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-slate-500">Loading...</p>
      ) : webhooks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-6 py-8 text-center">
          <p className="text-sm text-detec-slate-500">No webhooks configured.</p>
          <p className="text-xs text-detec-slate-600 mt-1">Add a webhook to receive event notifications.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <div
              key={wh.id}
              className="rounded-lg border border-detec-slate-700/40 bg-detec-slate-900/50 p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <code className="text-sm text-detec-slate-200 break-all">{wh.url}</code>
                  <div className="flex items-center gap-2 mt-1">
                    {wh.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-detec-slate-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-detec-slate-600" />Paused
                      </span>
                    )}
                    {wh.events.length > 0 && (
                      <span className="text-xs text-detec-slate-500">
                        {wh.events.length} event type{wh.events.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    {wh.events.length === 0 && (
                      <span className="text-xs text-detec-slate-500">All events</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => handleTest(wh.id)}
                    className="rounded px-2 py-1 text-xs text-detec-slate-400 hover:bg-detec-slate-800 transition-colors"
                  >
                    Test
                  </button>
                  <button
                    onClick={() => handleToggle(wh)}
                    className="rounded px-2 py-1 text-xs text-detec-slate-400 hover:bg-detec-slate-800 transition-colors"
                  >
                    {wh.is_active ? 'Pause' : 'Resume'}
                  </button>
                  <button
                    onClick={() => handleDelete(wh.id)}
                    className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950/40 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <details className="group">
                <summary className="text-xs text-detec-slate-500 cursor-pointer hover:text-detec-slate-400 transition-colors">
                  Signing secret
                </summary>
                <code className="mt-1 block text-xs text-detec-slate-400 break-all select-all">
                  {wh.secret}
                </code>
              </details>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <WebhookFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadWebhooks(); }}
        />
      )}

      {showTemplateModal && (
        <WebhookTemplateModal
          onClose={() => setShowTemplateModal(false)}
          onSaved={() => { setShowTemplateModal(false); loadWebhooks(); }}
          onError={(msg) => setError(msg)}
        />
      )}
    </div>
  );
}


function WebhookTemplateModal({ onClose, onSaved, onError }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [config, setConfig] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setFormError(null);
      try {
        const data = await fetchWebhookTemplates();
        if (!cancelled) setTemplates(data || []);
      } catch (err) {
        if (!cancelled) setFormError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const handleSelectTemplate = (t) => {
    setSelectedTemplate(t);
    const initial = {};
    for (const f of t.config_fields || []) {
      initial[f.key] = f.default || '';
    }
    setConfig(initial);
    setFormError(null);
  };

  const handleConfigChange = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTemplate) return;
    setFormError(null);
    const required = (selectedTemplate.config_fields || []).filter((f) => f.required);
    for (const f of required) {
      if (!(config[f.key] || '').trim()) {
        setFormError(`${f.label} is required`);
        return;
      }
    }
    setSubmitting(true);
    try {
      await createWebhookFromTemplate(selectedTemplate.id, config);
      onSaved();
    } catch (err) {
      setFormError(err.message);
      onError?.(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">Create Webhook from Template</h2>

        {loading ? (
          <p className="text-sm text-detec-slate-500">Loading templates...</p>
        ) : !selectedTemplate ? (
          <div className="space-y-2">
            <p className="text-xs text-detec-slate-500 mb-3">Choose a SIEM or integration template:</p>
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelectTemplate(t)}
                className="w-full text-left rounded-lg border border-detec-slate-700 bg-detec-slate-800/50 px-4 py-3 hover:border-detec-primary-500/30 hover:bg-detec-slate-800 transition-colors"
              >
                <div className="font-medium text-detec-slate-200">{t.name}</div>
                <div className="text-xs text-detec-slate-500 mt-0.5">{t.description}</div>
              </button>
            ))}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-detec-slate-200">{selectedTemplate.name}</h3>
              <button
                type="button"
                onClick={() => setSelectedTemplate(null)}
                className="text-xs text-detec-slate-500 hover:text-detec-slate-300"
              >
                Change template
              </button>
            </div>
            <p className="text-xs text-detec-slate-500">{selectedTemplate.description}</p>

            <div className="space-y-3">
              {(selectedTemplate.config_fields || []).map((f) => (
                <label key={f.key} className="block">
                  <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">
                    {f.label}
                    {f.required && <span className="text-red-400 ml-0.5">*</span>}
                  </span>
                  <input
                    type={f.secret ? 'password' : 'text'}
                    value={config[f.key] ?? ''}
                    onChange={(e) => handleConfigChange(f.key, e.target.value)}
                    placeholder={f.placeholder || f.default || ''}
                    spellCheck={false}
                    className="mt-1 w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:border-detec-primary-500 focus:outline-none"
                  />
                </label>
              ))}
            </div>

            {formError && (
              <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 disabled:opacity-50"
              >
                {submitting ? 'Creating...' : 'Create webhook'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}


const POSTURE_META = {
  passive: { label: 'Passive', color: 'bg-detec-slate-600/30 text-detec-slate-400', dot: 'bg-detec-slate-500' },
  audit:   { label: 'Audit',   color: 'bg-detec-amber-500/15 text-detec-amber-500', dot: 'bg-detec-amber-500' },
  active:  { label: 'Active',  color: 'bg-detec-enforce-block/15 text-detec-enforce-block', dot: 'bg-detec-enforce-block' },
};

const POSTURE_OPTIONS = [
  { value: 'passive', label: 'Passive', desc: 'Detect and report only' },
  { value: 'audit', label: 'Audit', desc: 'Log enforcement decisions without acting' },
  { value: 'active', label: 'Active', desc: 'Autonomous process termination', ownerOnly: true },
];

function TenantPostureSection() {
  const { user } = useAuth();
  const isOwner = user?.role === 'owner';

  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPosture, setSelectedPosture] = useState('passive');
  const [selectedThreshold, setSelectedThreshold] = useState(0.75);
  const [applyToAll, setApplyToAll] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPostureSummary();
      setSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 6000);
    return () => clearTimeout(t);
  }, [feedback]);

  function handleSave() {
    if (selectedPosture === 'active') {
      setShowConfirm(true);
      setConfirmInput('');
    } else {
      doSave();
    }
  }

  async function doSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateTenantPosture({
        enforcement_posture: selectedPosture,
        auto_enforce_threshold: selectedThreshold,
      });
      setFeedback({
        type: 'success',
        msg: `Tenant posture set to ${selectedPosture}. ${result.updated} endpoint${result.updated !== 1 ? 's' : ''} updated.`,
      });
      setShowConfirm(false);
      setApplyToAll(false);
      loadSummary();
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Failed to update tenant posture' });
    } finally {
      setSaving(false);
    }
  }

  const showThreshold = selectedPosture === 'audit' || selectedPosture === 'active';

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
        Enforcement Posture
      </h2>
      <p className="text-xs text-detec-slate-500">
        Set the default enforcement posture for all endpoints in this tenant.
        New endpoints inherit this posture on registration.
      </p>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {feedback && (
        <div className={`text-xs px-3 py-1.5 rounded detec-toast-enter ${
          feedback.type === 'success'
            ? 'bg-detec-teal-500/10 text-detec-teal-500 border border-detec-teal-500/20'
            : 'bg-detec-enforce-block/10 text-detec-enforce-block border border-red-800/50'
        }`}>
          {feedback.msg}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-detec-slate-500">Loading...</p>
      ) : (
        <>
          {/* Current posture distribution */}
          {summary && (
            <div className="flex gap-3 text-xs">
              {['passive', 'audit', 'active'].map((p) => {
                const meta = POSTURE_META[p];
                const count = summary[p] || 0;
                return (
                  <div key={p} className={`flex items-center gap-1.5 rounded px-2.5 py-1 ${meta.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                    <span>{meta.label}</span>
                    <span className="font-mono font-semibold">{count}</span>
                  </div>
                );
              })}
              <span className="text-detec-slate-600 self-center ml-1">
                {summary.total} endpoint{summary.total !== 1 ? 's' : ''} total
              </span>
            </div>
          )}

          {/* Three-state posture selector */}
          <div className="flex flex-col sm:flex-row gap-2">
            {POSTURE_OPTIONS.map((opt) => {
              const selected = selectedPosture === opt.value;
              const disabled = opt.ownerOnly && !isOwner;
              const meta = POSTURE_META[opt.value];
              return (
                <button
                  key={opt.value}
                  disabled={disabled}
                  onClick={() => !disabled && setSelectedPosture(opt.value)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-left transition-all ${
                    selected
                      ? `border-detec-primary-500/50 ${meta.color} ring-1 ring-detec-primary-500/30`
                      : disabled
                        ? 'border-detec-slate-700/50 bg-detec-slate-800/30 opacity-40 cursor-not-allowed'
                        : 'border-detec-slate-700 bg-detec-slate-800/50 hover:border-detec-slate-600 cursor-pointer'
                  }`}
                  title={disabled ? 'Owner role required for Active posture' : ''}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${selected ? meta.dot : 'bg-detec-slate-600'}`} />
                    <span className={`text-sm font-medium ${selected ? '' : 'text-detec-slate-400'}`}>{opt.label}</span>
                  </div>
                  <p className="text-xs text-detec-slate-500 mt-1">{opt.desc}</p>
                  {disabled && (
                    <p className="text-xs text-detec-enforce-warn mt-1">Owner only</p>
                  )}
                </button>
              );
            })}
          </div>

          {/* Threshold slider */}
          {showThreshold && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-detec-slate-400">
                  Auto-enforce threshold
                </label>
                <span className="text-sm font-mono text-detec-slate-200">{selectedThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.50"
                max="1.00"
                step="0.05"
                value={selectedThreshold}
                onChange={(e) => setSelectedThreshold(parseFloat(e.target.value))}
                className="w-full accent-detec-primary-500 cursor-pointer"
              />
              <div className="flex justify-between text-xs text-detec-slate-600">
                <span>0.50 (aggressive)</span>
                <span>1.00 (conservative)</span>
              </div>
            </div>
          )}

          {/* Apply to all checkbox */}
          <label className="flex items-start gap-2.5 cursor-pointer group">
            <input
              type="checkbox"
              checked={applyToAll}
              onChange={(e) => setApplyToAll(e.target.checked)}
              className="mt-0.5 rounded border-detec-slate-600 bg-detec-slate-900 text-detec-primary-500 focus:ring-detec-primary-500/30"
            />
            <div>
              <span className="text-sm text-detec-slate-300 group-hover:text-detec-slate-200 transition-colors">
                Apply to all existing endpoints
              </span>
              {summary && (
                <p className="text-xs text-detec-slate-500 mt-0.5">
                  Updates {summary.total} existing endpoint{summary.total !== 1 ? 's' : ''} to the selected posture and threshold
                </p>
              )}
            </div>
          </label>

          {/* Save */}
          <div className="flex items-center gap-3">
            <button
              disabled={!applyToAll || saving}
              onClick={handleSave}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                applyToAll && !saving
                  ? 'bg-detec-primary-500 hover:bg-detec-primary-600 text-white cursor-pointer'
                  : 'bg-detec-slate-700 text-detec-slate-500 cursor-not-allowed'
              }`}
            >
              {saving ? 'Saving...' : 'Save Enforcement Defaults'}
            </button>
            {!applyToAll && (
              <span className="text-xs text-detec-slate-600">
                Check "Apply to all" to enable saving
              </span>
            )}
          </div>
        </>
      )}

      {showConfirm && (
        <ConfirmActiveTenantModal
          endpointCount={summary?.total || 0}
          threshold={selectedThreshold}
          confirmInput={confirmInput}
          onInputChange={setConfirmInput}
          onConfirm={doSave}
          onCancel={() => setShowConfirm(false)}
          saving={saving}
        />
      )}
    </div>
  );
}

const CONFIRM_PHRASE = 'ENABLE ACTIVE';

function ConfirmActiveTenantModal({ endpointCount, threshold, confirmInput, onInputChange, onConfirm, onCancel, saving }) {
  const confirmed = confirmInput === CONFIRM_PHRASE;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onCancel}>
      <div
        className="w-full max-w-lg rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-4 sm:p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-detec-slate-100">Enable Active Enforcement for All Endpoints</h2>

        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 p-4 text-sm text-detec-enforce-block space-y-2">
          <p className="font-semibold">This is a destructive, tenant-wide action.</p>
          <p>
            Active enforcement enables <strong>autonomous process termination</strong> on
            all <strong>{endpointCount}</strong> endpoint{endpointCount !== 1 ? 's' : ''} in
            this tenant. Agents will automatically kill processes that exceed the confidence
            threshold of <strong>{threshold.toFixed(2)}</strong> without human approval.
          </p>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-detec-slate-500">Endpoints affected</span>
              <p className="text-detec-slate-200 font-mono">{endpointCount}</p>
            </div>
            <div>
              <span className="text-detec-slate-500">Threshold</span>
              <p className="text-detec-slate-200 font-mono">{threshold.toFixed(2)}</p>
            </div>
          </div>

          <div>
            <label className="block text-sm text-detec-slate-400 mb-1.5">
              Type <span className="font-mono text-detec-slate-200">{CONFIRM_PHRASE}</span> to confirm
            </label>
            <input
              type="text"
              value={confirmInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder={CONFIRM_PHRASE}
              autoFocus
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:ring-1 focus:ring-detec-enforce-block/50"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-lg text-detec-slate-400 hover:text-detec-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={!confirmed || saving}
            onClick={onConfirm}
            className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
              confirmed && !saving
                ? 'bg-detec-enforce-block text-white hover:bg-red-600 cursor-pointer'
                : 'bg-detec-slate-700 text-detec-slate-500 cursor-not-allowed'
            }`}
          >
            {saving ? 'Enabling...' : 'Enable Active Enforcement'}
          </button>
        </div>
      </div>
    </div>
  );
}


const PATTERN_TYPES = [
  { value: 'name', label: 'Name' },
  { value: 'path', label: 'Path' },
  { value: 'hash', label: 'Hash' },
];

function AllowListSection() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAllowList();
      setEntries(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleDelete = async (id, pattern) => {
    if (!confirm(`Remove "${pattern}" from the allow list?`)) return;
    try {
      await deleteAllowListEntry(id);
      loadEntries();
    } catch (err) {
      setError(err.message);
    }
  };

  const fmtDate = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
          Enforcement Allow List
        </h2>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-detec-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-detec-primary-500 transition-colors"
        >
          Add entry
        </button>
      </div>

      <p className="text-xs text-detec-slate-500">
        Tools matching an allow-list entry are exempt from enforcement actions regardless of posture or policy.
      </p>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-slate-500">Loading...</p>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-6 py-8 text-center">
          <p className="text-sm text-detec-slate-500">No allow-list entries.</p>
          <p className="text-xs text-detec-slate-600 mt-1">Add an entry to exempt specific tools from enforcement.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-detec-slate-700/40 text-xs font-medium text-detec-slate-500 uppercase tracking-wider">
                <th className="pb-2 pr-4">Pattern</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Description</th>
                <th className="pb-2 pr-4">Created by</th>
                <th className="pb-2 pr-4">Created</th>
                <th className="pb-2 w-16" />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-detec-slate-700/20">
                  <td className="py-2.5 pr-4">
                    <code className="text-xs text-detec-slate-200 break-all">{entry.pattern}</code>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="inline-block rounded bg-detec-slate-700/50 px-2 py-0.5 text-xs text-detec-slate-400">
                      {entry.pattern_type}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-slate-400">
                    {entry.description || <span className="text-detec-slate-600 italic">none</span>}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-slate-400">
                    {entry.created_by || <span className="text-detec-slate-600">unknown</span>}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-detec-slate-500 whitespace-nowrap">
                    {fmtDate(entry.created_at)}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      onClick={() => handleDelete(entry.id, entry.pattern)}
                      className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950/40 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <AllowListFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadEntries(); }}
        />
      )}
    </div>
  );
}

function AllowListFormModal({ onClose, onSaved }) {
  const [pattern, setPattern] = useState('');
  const [patternType, setPatternType] = useState('name');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    const trimmed = pattern.trim();
    if (!trimmed) { setFormError('Pattern is required'); return; }
    if (trimmed.length < 3) { setFormError('Pattern must be at least 3 characters'); return; }

    setSubmitting(true);
    try {
      await addAllowListEntry({
        pattern: trimmed,
        pattern_type: patternType,
        description: description.trim() || undefined,
      });
      onSaved();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">Add Allow-List Entry</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">Pattern</label>
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder="e.g. ollama, /usr/local/bin/ollama, sha256:abc..."
              required
              spellCheck={false}
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 font-mono focus:border-detec-primary-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">Match Type</label>
            <select
              value={patternType}
              onChange={(e) => setPatternType(e.target.value)}
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
            >
              {PATTERN_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>{pt.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-detec-slate-600">
              {patternType === 'name' && 'Match by tool or process name (e.g. "ollama")'}
              {patternType === 'path' && 'Match by full executable path (e.g. "/usr/local/bin/ollama")'}
              {patternType === 'hash' && 'Match by binary SHA-256 hash'}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">
              Description <span className="font-normal text-detec-slate-600">(optional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Why this tool is exempt"
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
            />
          </div>

          {formError && (
            <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 disabled:opacity-50"
            >
              {submitting ? 'Adding...' : 'Add entry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DisabledServicesSection() {
  const [endpoints, setEndpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [restoring, setRestoring] = useState({});
  const [feedback, setFeedback] = useState(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchDisabledServices();
      setEndpoints(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRestore = async (endpointId, serviceId, unitName) => {
    if (!confirm(`Restore service "${unitName}" on this endpoint?`)) return;
    setRestoring((prev) => ({ ...prev, [serviceId]: true }));
    setFeedback(null);
    try {
      await restoreServices(endpointId, [serviceId]);
      setFeedback({ type: 'success', text: `Restore queued for ${unitName}. The agent will re-enable it on the next heartbeat.` });
      loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setRestoring((prev) => ({ ...prev, [serviceId]: false }));
    }
  };

  const handleRestoreAll = async (endpointId, hostname) => {
    if (!confirm(`Restore all disabled services on ${hostname}?`)) return;
    setRestoring((prev) => ({ ...prev, [endpointId]: true }));
    setFeedback(null);
    try {
      const result = await restoreServices(endpointId);
      setFeedback({ type: 'success', text: `${result.queued} service(s) queued for restoration on ${hostname}.` });
      loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setRestoring((prev) => ({ ...prev, [endpointId]: false }));
    }
  };

  const fmtDate = (ts) => {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const totalServices = endpoints.reduce((sum, ep) => sum + (ep.disabled_services?.length || 0), 0);

  return (
    <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-detec-slate-300 uppercase tracking-wider">
          Disabled Services
        </h2>
        {totalServices > 0 && (
          <span className="rounded-full bg-detec-enforce-block/15 px-2.5 py-0.5 text-xs font-medium text-detec-enforce-block">
            {totalServices} disabled
          </span>
        )}
      </div>

      <p className="text-xs text-detec-slate-500">
        Services disabled by anti-resurrection escalation (repeated enforcement kills). Restoring re-enables the service unit on the endpoint.
      </p>

      {feedback && (
        <div className={`rounded-lg border px-3 py-2 text-xs ${
          feedback.type === 'success'
            ? 'border-detec-teal-500/30 bg-detec-teal-900/20 text-detec-teal-400'
            : 'border-red-800/50 bg-red-950/30 text-red-400'
        }`}>
          {feedback.text}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-detec-slate-500">Loading...</p>
      ) : endpoints.length === 0 ? (
        <div className="rounded-lg border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-6 py-8 text-center">
          <p className="text-sm text-detec-slate-500">No disabled services across any endpoints.</p>
          <p className="text-xs text-detec-slate-600 mt-1">Services appear here when anti-resurrection escalation disables a systemd unit or launchd plist.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {endpoints.map((ep) => (
            <div key={ep.endpoint_id} className="rounded-lg border border-detec-slate-700/40 bg-detec-slate-900/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-detec-slate-200">{ep.hostname}</span>
                  <span className="text-xs text-detec-slate-500 font-mono">{ep.endpoint_id.slice(0, 8)}</span>
                </div>
                {ep.disabled_services?.length > 1 && (
                  <button
                    onClick={() => handleRestoreAll(ep.endpoint_id, ep.hostname)}
                    disabled={restoring[ep.endpoint_id]}
                    className="rounded-lg border border-detec-teal-500/30 px-2.5 py-1 text-xs font-medium text-detec-teal-400 hover:bg-detec-teal-500/10 disabled:opacity-50 transition-colors"
                  >
                    {restoring[ep.endpoint_id] ? 'Queuing...' : 'Restore all'}
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-detec-slate-500 border-b border-detec-slate-700/30">
                      <th className="text-left py-1.5 pr-3 font-medium">Unit</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Type</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Tool</th>
                      <th className="text-left py-1.5 pr-3 font-medium">Disabled</th>
                      <th className="text-right py-1.5 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ep.disabled_services.map((svc) => (
                      <tr key={svc.service_id} className="border-b border-detec-slate-700/20 last:border-0">
                        <td className="py-2 pr-3 font-mono text-detec-slate-300">{svc.unit_name}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                            svc.service_type === 'systemd'
                              ? 'bg-blue-500/15 text-blue-400'
                              : 'bg-purple-500/15 text-purple-400'
                          }`}>
                            {svc.service_type}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-detec-slate-400">{svc.tool_name || 'N/A'}</td>
                        <td className="py-2 pr-3 text-detec-slate-500">{fmtDate(svc.disabled_at)}</td>
                        <td className="py-2 text-right">
                          <button
                            onClick={() => handleRestore(ep.endpoint_id, svc.service_id, svc.unit_name)}
                            disabled={restoring[svc.service_id]}
                            className="rounded-lg bg-detec-teal-600 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-detec-teal-500 disabled:opacity-50 transition-colors"
                          >
                            {restoring[svc.service_id] ? 'Queuing...' : 'Restore'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function WebhookFormModal({ onClose, onSaved }) {
  const [url, setUrl] = useState('');
  const [selectedEvents, setSelectedEvents] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  const toggleEvent = (event) => {
    setSelectedEvents(prev =>
      prev.includes(event)
        ? prev.filter(e => e !== event)
        : [...prev, event]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    if (!url.trim()) { setFormError('URL is required'); return; }

    setSubmitting(true);
    try {
      await createWebhook({ url: url.trim(), events: selectedEvents });
      onSaved();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-4 sm:p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-detec-slate-100 mb-4">Add Webhook</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-1">Endpoint URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/webhook"
              required
              className="w-full rounded-lg border border-detec-slate-700 bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-200 focus:border-detec-primary-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-detec-slate-400 mb-2">
              Event types <span className="font-normal text-detec-slate-600">(leave empty for all)</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {EVENT_TYPES.map((evt) => (
                <label
                  key={evt}
                  className="flex items-center gap-2 rounded-lg border border-detec-slate-700/40 bg-detec-slate-800/50 px-3 py-2 cursor-pointer hover:border-detec-primary-500/30 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(evt)}
                    onChange={() => toggleEvent(evt)}
                    className="rounded border-detec-slate-600 bg-detec-slate-900 text-detec-primary-500 focus:ring-detec-primary-500/30"
                  />
                  <span className="text-xs text-detec-slate-300">{evt}</span>
                </label>
              ))}
            </div>
          </div>

          {formError && (
            <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">{formError}</div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-detec-slate-700 px-4 py-2 text-sm text-detec-slate-400 hover:bg-detec-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-detec-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-detec-primary-500 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create webhook'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
