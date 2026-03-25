import { useEffect, useState } from 'react';

/**
 * Toast — minimal auto-dismissing notification.
 *
 * Usage:
 *   const [toast, setToast] = useState(null);
 *   setToast({ message: 'Done!', variant: 'success' });
 *   <Toast toast={toast} onDismiss={() => setToast(null)} />
 *
 * Props:
 *   toast    — { message: string, variant?: 'success' | 'error' } or null
 *   onDismiss — called when the toast self-dismisses or is closed
 *   duration  — ms before auto-dismiss (default 3000)
 */
export default function Toast({ toast, onDismiss, duration = 3000 }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!toast) {
      setVisible(false);
      return;
    }
    setVisible(true);
    const t = setTimeout(() => {
      setVisible(false);
      onDismiss?.();
    }, duration);
    return () => clearTimeout(t);
  }, [toast, duration, onDismiss]);

  if (!toast || !visible) return null;

  const isError = toast.variant === 'error';

  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        'fixed bottom-5 right-5 z-[200] max-w-sm w-full sm:w-auto',
        'flex items-center gap-3 px-4 py-3 rounded-detec shadow-detec-card',
        'border text-sm font-medium transition-all',
        isError
          ? 'bg-detec-enforce-block/20 border-detec-enforce-block/40 text-detec-enforce-block'
          : 'bg-detec-ui-surface border-detec-ui-border text-detec-ui-text',
      ].join(' ')}
    >
      {isError ? (
        <svg className="shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      ) : (
        <svg className="shrink-0 text-detec-ui-accent" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
      <span className="flex-1">{toast.message}</span>
      <button
        type="button"
        onClick={() => { setVisible(false); onDismiss?.(); }}
        className="shrink-0 text-detec-ui-muted hover:text-detec-ui-text"
        aria-label="Dismiss"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
