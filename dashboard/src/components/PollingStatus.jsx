import { useState, useEffect } from 'react';

const FRESH_SEC = 120;
const STALE_SEC = 900;

function freshnessDotClass(secs) {
  if (secs == null) return 'bg-detec-slate-500';
  if (secs < FRESH_SEC) return 'bg-detec-teal-500';
  if (secs < STALE_SEC) return 'bg-detec-amber-500';
  return 'bg-detec-enforce-block';
}

export default function PollingStatus({ lastUpdated, paused, onTogglePause }) {
  const [ago, setAgo] = useState('');
  const [secs, setSecs] = useState(null);

  useEffect(() => {
    if (!lastUpdated) return;
    const update = () => {
      const s = Math.round((Date.now() - lastUpdated) / 1000);
      setSecs(s);
      if (s < 5) setAgo('just now');
      else if (s < 60) setAgo(`${s}s ago`);
      else setAgo(`${Math.floor(s / 60)}m ago`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [lastUpdated]);

  const dotClass = !paused && lastUpdated ? freshnessDotClass(secs) : 'bg-detec-slate-500';

  return (
    <div className="flex items-center gap-2 text-xs text-detec-slate-500">
      {lastUpdated && (
        <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotClass}`} aria-hidden="true" />
      )}
      <span>{paused ? 'Paused' : (lastUpdated ? `Updated ${ago}` : 'Updated never')}</span>
      <button
        onClick={onTogglePause}
        className="ml-0.5 hover:text-detec-slate-300 transition-colors"
        aria-label={paused ? 'Resume auto-refresh' : 'Pause auto-refresh'}
      >
        {paused ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
          </svg>
        )}
      </button>
    </div>
  );
}
