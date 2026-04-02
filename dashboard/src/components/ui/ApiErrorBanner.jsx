/**
 * ApiErrorBanner — displays an API error in a consistent inline banner.
 *
 * Props:
 *   error      {string|null}  The error message to display.  Renders nothing when null/falsy.
 *   onDismiss  {function}     Optional dismiss callback.  Omit to make the banner non-dismissible.
 *   className  {string}       Extra Tailwind classes (appended to the outer div).
 */
export default function ApiErrorBanner({ error, onDismiss, className = '' }) {
  if (!error) return null;

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-lg border border-red-700/50 bg-red-900/20 px-4 py-3 text-sm text-red-300 ${className}`}
    >
      {/* Warning icon */}
      <svg
        className="mt-0.5 h-4 w-4 shrink-0 text-red-400"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
          clipRule="evenodd"
        />
      </svg>

      <span className="flex-1">{error}</span>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="ml-auto shrink-0 rounded p-0.5 text-red-400 hover:bg-red-800/40 hover:text-red-200 transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      )}
    </div>
  );
}
