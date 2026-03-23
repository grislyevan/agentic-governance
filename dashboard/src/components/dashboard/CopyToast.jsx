import { useState, useCallback } from 'react';

/**
 * Lightweight copy-to-clipboard with inline toast feedback.
 * Shows a brief "Copied" confirmation that fades out.
 *
 * Usage:
 *   const { copied, copy } = useCopyToast();
 *   <button onClick={() => copy(text)}>Copy</button>
 *   {copied && <CopyToast />}
 */
export function useCopyToast(duration = 1600) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async (text) => {
    try {
      await navigator.clipboard?.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), duration);
    } catch {
      // Clipboard API unavailable — silent fallback
    }
  }, [duration]);

  return { copied, copy };
}

export default function CopyToast({ message = 'Copied' }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-detec-teal-500 detec-toast-enter">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="20 6 9 17 4 12" />
      </svg>
      {message}
    </span>
  );
}
