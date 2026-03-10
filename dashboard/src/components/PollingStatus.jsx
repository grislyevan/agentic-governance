import { useState, useEffect } from 'react';

export default function PollingStatus({ lastUpdated, paused, onTogglePause }) {
  const [ago, setAgo] = useState('');

  useEffect(() => {
    if (!lastUpdated) return;
    const update = () => {
      const secs = Math.round((Date.now() - lastUpdated) / 1000);
      if (secs < 5) setAgo('just now');
      else if (secs < 60) setAgo(`${secs}s ago`);
      else setAgo(`${Math.floor(secs / 60)}m ago`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [lastUpdated]);

  return (
    <div className="flex items-center gap-2 text-xs text-detec-slate-500">
      {!paused && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-detec-teal-500 opacity-40" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-detec-teal-500" />
        </span>
      )}
      <span>{paused ? 'Paused' : `Updated ${ago}`}</span>
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
