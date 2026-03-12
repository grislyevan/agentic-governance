import { useState, useEffect } from 'react';
import { getApiConfig, updateEndpointPosture } from '../../lib/api';
import useAuth from '../../hooks/useAuth';

const POSTURE_META = {
  passive:  { label: 'Passive', color: 'bg-detec-slate-600/30 text-detec-slate-400', dot: 'bg-detec-slate-500' },
  audit:    { label: 'Audit',   color: 'bg-detec-amber-500/15 text-detec-amber-500', dot: 'bg-detec-amber-500' },
  active:   { label: 'Active',  color: 'bg-detec-enforce-block/15 text-detec-enforce-block', dot: 'bg-detec-enforce-block' },
};

export default function EndpointContextBar({ endpointCount, endpoints, endpointStatuses = [], onPostureChange }) {
  const multipleEndpoints = endpoints?.length > 1;
  const firstEp = endpoints?.[0];

  const hostname = multipleEndpoints ? 'Multiple' : (firstEp?.hostname || 'N/A');
  const os = multipleEndpoints ? 'Various' : (firstEp?.os_info || 'N/A');
  const managementState = multipleEndpoints ? null : (firstEp?.management_state || 'unmanaged');

  const enforcementPosture = firstEp?.enforcement_posture || 'passive';
  const currentThreshold = firstEp?.auto_enforce_threshold ?? 0.75;

  const lastSeen = firstEp?.last_seen_at
    ? timeSince(new Date(firstEp.last_seen_at))
    : 'N/A';

  const config = getApiConfig();
  const apiKeyDisplay = config.apiKey && config.apiKey.length >= 4
    ? `${config.apiKey.slice(0, 4)}${'*'.repeat(4)}`
    : config.apiKey ? '****' : 'Not configured';

  const statusCounts = computeStatusCounts(endpointStatuses, endpoints);

  const { user } = useAuth();
  const isOwner = user?.role === 'owner';

  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedPosture, setSelectedPosture] = useState(enforcementPosture);
  const [selectedThreshold, setSelectedThreshold] = useState(currentThreshold);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    setSelectedPosture(enforcementPosture);
    setSelectedThreshold(currentThreshold);
  }, [enforcementPosture, currentThreshold]);

  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 5000);
    return () => clearTimeout(t);
  }, [feedback]);

  const showSingleEndpoint = !multipleEndpoints && firstEp;
  const postureMeta = POSTURE_META[enforcementPosture] || POSTURE_META.passive;
  const hasChanges = selectedPosture !== enforcementPosture || selectedThreshold !== currentThreshold;

  function handleApply() {
    if (selectedPosture === 'active' && enforcementPosture !== 'active') {
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
      await updateEndpointPosture(firstEp.id, {
        enforcement_posture: selectedPosture,
        auto_enforce_threshold: selectedThreshold,
      });
      setFeedback({ type: 'success', msg: `Enforcement posture set to ${selectedPosture}` });
      setPanelOpen(false);
      setShowConfirm(false);
      onPostureChange?.();
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Failed to update posture' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      {/* Context bar */}
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

        {managementState && (
          <>
            <span className="flex items-center gap-1.5">
              <span className="text-detec-slate-500 text-xs">Mgmt:</span>
              <span className={`font-mono text-xs px-2 py-0.5 rounded ${managementState === 'managed' ? 'bg-detec-teal-500/15 text-detec-teal-500' : 'bg-detec-amber-500/15 text-detec-amber-500'}`}>
                {managementState === 'managed' ? 'Conformant' : 'Nonconformant'}
              </span>
            </span>
            <Sep />
          </>
        )}

        {showSingleEndpoint && (
          <>
            <span className="flex items-center gap-1.5">
              <span className="text-detec-slate-500 text-xs">Enforce:</span>
              <button
                onClick={() => setPanelOpen(!panelOpen)}
                className={`font-mono text-xs px-2 py-0.5 rounded cursor-pointer transition-colors hover:ring-1 hover:ring-detec-slate-500 ${postureMeta.color}`}
                title="Click to change enforcement posture"
              >
                <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${postureMeta.dot}`} />
                {postureMeta.label}
              </button>
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

      {/* Inline feedback */}
      {feedback && (
        <div className={`text-xs px-3 py-1.5 rounded detec-toast-enter ${
          feedback.type === 'success'
            ? 'bg-detec-teal-500/10 text-detec-teal-500'
            : 'bg-detec-enforce-block/10 text-detec-enforce-block'
        }`}>
          {feedback.msg}
        </div>
      )}

      {/* Posture control panel */}
      {panelOpen && showSingleEndpoint && (
        <PosturePanel
          hostname={hostname}
          selectedPosture={selectedPosture}
          selectedThreshold={selectedThreshold}
          onPostureChange={setSelectedPosture}
          onThresholdChange={setSelectedThreshold}
          onApply={handleApply}
          onCancel={() => { setPanelOpen(false); setSelectedPosture(enforcementPosture); setSelectedThreshold(currentThreshold); }}
          hasChanges={hasChanges}
          saving={saving}
          isOwner={isOwner}
        />
      )}

      {/* Confirmation modal for active posture */}
      {showConfirm && (
        <ConfirmActiveModal
          hostname={hostname}
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


function PosturePanel({ hostname, selectedPosture, selectedThreshold, onPostureChange, onThresholdChange, onApply, onCancel, hasChanges, saving, isOwner }) {
  const postureOptions = [
    { value: 'passive', label: 'Passive', desc: 'Detect and report only' },
    { value: 'audit', label: 'Audit', desc: 'Log enforcement decisions without acting' },
    { value: 'active', label: 'Active', desc: 'Autonomous process termination', ownerOnly: true },
  ];

  const showThreshold = selectedPosture === 'audit' || selectedPosture === 'active';

  return (
    <div className="rounded-lg border border-detec-slate-700 bg-detec-slate-800/80 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-detec-slate-200">
          Enforcement Posture
          <span className="ml-2 text-detec-slate-500 font-normal">{hostname}</span>
        </h3>
        <button onClick={onCancel} className="text-detec-slate-500 hover:text-detec-slate-300 text-xs">
          Cancel
        </button>
      </div>

      {/* Three-state selector */}
      <div className="flex gap-2">
        {postureOptions.map((opt) => {
          const selected = selectedPosture === opt.value;
          const disabled = opt.ownerOnly && !isOwner;
          const meta = POSTURE_META[opt.value];
          return (
            <button
              key={opt.value}
              disabled={disabled}
              onClick={() => !disabled && onPostureChange(opt.value)}
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
            onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
            className="w-full accent-detec-primary-500 cursor-pointer"
          />
          <div className="flex justify-between text-xs text-detec-slate-600">
            <span>0.50 (aggressive)</span>
            <span>1.00 (conservative)</span>
          </div>
        </div>
      )}

      {/* Apply button */}
      <div className="flex justify-end">
        <button
          disabled={!hasChanges || saving}
          onClick={onApply}
          className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
            hasChanges && !saving
              ? 'bg-detec-primary-500 text-white hover:bg-detec-primary-600 cursor-pointer'
              : 'bg-detec-slate-700 text-detec-slate-500 cursor-not-allowed'
          }`}
        >
          {saving ? 'Saving...' : 'Apply'}
        </button>
      </div>
    </div>
  );
}


function ConfirmActiveModal({ hostname, threshold, confirmInput, onInputChange, onConfirm, onCancel, saving }) {
  const confirmed = confirmInput === hostname;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div
        className="w-full max-w-lg rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-6 shadow-2xl space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-detec-slate-100">Enable Active Enforcement</h2>

        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 p-4 text-sm text-detec-enforce-block space-y-2">
          <p className="font-semibold">This is a destructive action.</p>
          <p>
            Active enforcement enables <strong>autonomous process termination</strong>.
            The agent on <strong>{hostname}</strong> will automatically kill
            processes that exceed the confidence threshold of <strong>{threshold.toFixed(2)}</strong> without
            human approval.
          </p>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-detec-slate-500">Hostname</span>
              <p className="text-detec-slate-200 font-mono">{hostname}</p>
            </div>
            <div>
              <span className="text-detec-slate-500">Threshold</span>
              <p className="text-detec-slate-200 font-mono">{threshold.toFixed(2)}</p>
            </div>
          </div>

          <div>
            <label className="block text-sm text-detec-slate-400 mb-1.5">
              Type <span className="font-mono text-detec-slate-200">{hostname}</span> to confirm
            </label>
            <input
              type="text"
              value={confirmInput}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder={hostname}
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
