import { useState, useEffect, useCallback } from 'react';
import { fetchPostureSummary, updateTenantPosture } from '../../lib/api';
import useAuth from '../../hooks/useAuth';

const POSTURE_CARDS = [
  {
    key: 'passive',
    label: 'Passive',
    desc: 'Detect only',
    bg: 'bg-detec-slate-600/20',
    border: 'border-detec-slate-600/30',
    text: 'text-detec-slate-400',
    dot: 'bg-detec-slate-500',
  },
  {
    key: 'audit',
    label: 'Audit',
    desc: 'Log decisions',
    bg: 'bg-detec-amber-500/10',
    border: 'border-detec-amber-500/20',
    text: 'text-detec-amber-500',
    dot: 'bg-detec-amber-500',
  },
  {
    key: 'active',
    label: 'Active',
    desc: 'Auto-enforce',
    bg: 'bg-detec-enforce-block/10',
    border: 'border-detec-enforce-block/20',
    text: 'text-detec-enforce-block',
    dot: 'bg-detec-enforce-block',
  },
];

export default function PostureSummaryWidget({ onPostureReset }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showKillSwitch, setShowKillSwitch] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const { user } = useAuth();
  const isOwner = user?.role === 'owner';

  const load = useCallback(async () => {
    try {
      const result = await fetchPostureSummary();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 5000);
    return () => clearTimeout(t);
  }, [feedback]);

  async function handleKillSwitch() {
    setResetting(true);
    try {
      await updateTenantPosture({ enforcement_posture: 'passive' });
      setFeedback({ type: 'success', msg: 'All endpoints set to passive' });
      setShowKillSwitch(false);
      load();
      onPostureReset?.();
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'Failed to reset posture' });
    } finally {
      setResetting(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/40 p-5">
        <div className="flex items-center gap-2 text-sm text-detec-slate-500">
          <span className="inline-block w-3 h-3 border-2 border-detec-slate-600 border-t-detec-primary-500 rounded-full animate-spin" />
          Loading posture data...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-detec-enforce-block/20 bg-detec-enforce-block/5 px-5 py-4 text-sm text-detec-enforce-block">
        Failed to load posture summary: {error}
      </div>
    );
  }

  const hasActiveEndpoints = (data?.audit || 0) + (data?.active || 0) > 0;

  return (
    <div className="space-y-2">
      <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/40 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <PostureIcon />
            <h2 className="text-sm font-semibold text-detec-slate-200">Enforcement Posture</h2>
            <span className="text-xs text-detec-slate-500 font-normal">
              {data?.total ?? 0} endpoint{data?.total !== 1 ? 's' : ''}
            </span>
          </div>

          {isOwner && hasActiveEndpoints && (
            <button
              onClick={() => setShowKillSwitch(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-detec-enforce-block/30 text-detec-enforce-block hover:bg-detec-enforce-block/10 transition-colors cursor-pointer"
            >
              <KillSwitchIcon />
              Set All Passive
            </button>
          )}
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {POSTURE_CARDS.map((card) => {
            const count = data?.[card.key] ?? 0;
            const pct = data?.total ? Math.round((count / data.total) * 100) : 0;
            return (
              <div
                key={card.key}
                className={`rounded-lg border ${card.border} ${card.bg} px-4 py-3 flex items-center justify-between`}
              >
                <div className="flex items-center gap-2.5">
                  <span className={`w-2 h-2 rounded-full ${card.dot}`} />
                  <div>
                    <span className={`text-sm font-medium ${card.text}`}>{card.label}</span>
                    <p className="text-xs text-detec-slate-600">{card.desc}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xl font-bold ${card.text}`}>{count}</span>
                  {data?.total > 0 && (
                    <p className="text-xs text-detec-slate-600">{pct}%</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Distribution bar */}
        {data?.total > 0 && (
          <div className="flex h-1.5 rounded-full overflow-hidden bg-detec-slate-700/50">
            {data.passive > 0 && (
              <div
                className="bg-detec-slate-500 transition-all"
                style={{ width: `${(data.passive / data.total) * 100}%` }}
              />
            )}
            {data.audit > 0 && (
              <div
                className="bg-detec-amber-500 transition-all"
                style={{ width: `${(data.audit / data.total) * 100}%` }}
              />
            )}
            {data.active > 0 && (
              <div
                className="bg-detec-enforce-block transition-all"
                style={{ width: `${(data.active / data.total) * 100}%` }}
              />
            )}
          </div>
        )}
      </div>

      {/* Feedback toast */}
      {feedback && (
        <div className={`text-xs px-3 py-1.5 rounded detec-toast-enter ${
          feedback.type === 'success'
            ? 'bg-detec-teal-500/10 text-detec-teal-500'
            : 'bg-detec-enforce-block/10 text-detec-enforce-block'
        }`}>
          {feedback.msg}
        </div>
      )}

      {/* Kill switch confirmation modal */}
      {showKillSwitch && (
        <KillSwitchModal
          activeCount={(data?.audit || 0) + (data?.active || 0)}
          onConfirm={handleKillSwitch}
          onCancel={() => setShowKillSwitch(false)}
          resetting={resetting}
        />
      )}
    </div>
  );
}


function KillSwitchModal({ activeCount, onConfirm, onCancel, resetting }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-0" onClick={onCancel}>
      <div
        className="w-full max-w-md rounded-xl border border-detec-slate-700 bg-detec-slate-900 p-4 sm:p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-detec-slate-100">Reset All Endpoints to Passive</h2>

        <div className="rounded-lg border border-detec-enforce-approval/30 bg-detec-enforce-approval/10 p-4 text-sm text-detec-enforce-approval space-y-2">
          <p className="font-semibold">This will disable all enforcement.</p>
          <p>
            {activeCount} endpoint{activeCount !== 1 ? 's' : ''} currently in audit or active
            posture will be switched to passive. All autonomous enforcement will stop immediately.
          </p>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="text-sm px-4 py-1.5 rounded-lg text-detec-slate-400 hover:text-detec-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={resetting}
            onClick={onConfirm}
            className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
              !resetting
                ? 'bg-detec-enforce-approval text-white hover:bg-orange-600 cursor-pointer'
                : 'bg-detec-slate-700 text-detec-slate-500 cursor-not-allowed'
            }`}
          >
            {resetting ? 'Resetting...' : 'Confirm: Set All Passive'}
          </button>
        </div>
      </div>
    </div>
  );
}


function PostureIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function KillSwitchIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
    </svg>
  );
}
