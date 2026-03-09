import { useState, useRef, useEffect } from 'react';
import { getApiConfig, setApiConfig } from '../lib/api';

export default function SettingsPage() {
  const config = getApiConfig();
  const [apiUrl, setApiUrl] = useState(config.apiUrl);
  const [apiKey, setApiKey] = useState(config.apiKey);
  const [saved, setSaved] = useState(false);
  const savedTimer = useRef(null);

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

      <div className="max-w-lg space-y-5">
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
      </div>
    </div>
  );
}
