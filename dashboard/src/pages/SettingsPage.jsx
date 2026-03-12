import { useState, useRef, useEffect, useCallback } from 'react';
import { getApiConfig, setApiConfig, fetchWebhooks, createWebhook, updateWebhook, deleteWebhook, testWebhook, downloadAgent, enrollAgentByEmail, fetchAllowList, addAllowListEntry, deleteAllowListEntry } from '../lib/api';
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
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-detec-slate-100">Settings</h1>

      <div className="max-w-2xl space-y-6">
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

        {canManageWebhooks && <AgentDownloadSection />}

        {canManageWebhooks && <WebhooksSection />}

        {canManageWebhooks && <AllowListSection />}
      </div>
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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
        <div className="flex gap-2">
          <input
            type="email"
            value={enrollEmail}
            onChange={(e) => setEnrollEmail(e.target.value)}
            placeholder="user@company.com"
            spellCheck={false}
            className="flex-1 bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 font-mono placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
          />
          <button
            onClick={handleEnroll}
            disabled={enrolling || !enrollEmail.trim()}
            className="px-4 py-2 bg-detec-primary-600 hover:bg-detec-primary-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
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
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-detec-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-detec-primary-500 transition-colors"
        >
          Add webhook
        </button>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl"
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
            <div className="grid grid-cols-2 gap-2">
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
