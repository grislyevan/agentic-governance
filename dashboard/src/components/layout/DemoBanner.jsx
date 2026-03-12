import { useState, useEffect } from 'react';
import { fetchDemoStatus } from '../../lib/api';

export default function DemoBanner() {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchDemoStatus()
      .then((data) => {
        if (!cancelled && data?.demo_mode) setVisible(true);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!visible || dismissed) return null;

  return (
    <div className="relative flex items-center justify-center gap-2 bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-xs text-amber-400">
      <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" />
      </svg>
      <span>Demo Environment &mdash; Showing sample data</span>
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-3 text-amber-400/60 hover:text-amber-400 transition-colors"
        aria-label="Dismiss demo banner"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
