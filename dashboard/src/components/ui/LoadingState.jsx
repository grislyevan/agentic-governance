/**
 * LoadingState — a centred spinner placeholder for page-level data loading.
 *
 * Props:
 *   message  {string}  Optional text shown below the spinner (default: "Loading…")
 *   className {string} Extra Tailwind classes for the wrapper div.
 */
import ApertureSpinner from '../branding/ApertureSpinner';

export default function LoadingState({ message = 'Loading\u2026', className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-20 text-detec-ink-secondary ${className}`}
      aria-busy="true"
      aria-label={message}
    >
      <ApertureSpinner size="sm" />
      {message && (
        <span className="text-sm">{message}</span>
      )}
    </div>
  );
}
