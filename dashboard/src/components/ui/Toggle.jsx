/**
 * Shared toggle (checkbox-style switch). Light enterprise: no neon focus.
 */
export default function Toggle({ checked, onChange, disabled, label, className = '' }) {
  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer ${disabled ? 'opacity-60 cursor-not-allowed' : ''} ${className}`}>
      <span className="relative inline-flex h-6 w-10 flex-shrink-0 rounded-full border border-detec-ui-border bg-white shadow-detec-sm transition-colors focus-within:ring-2 focus-within:ring-detec-ui-accent/20 focus-within:border-detec-ui-accent">
        <input
          type="checkbox"
          checked={!!checked}
          onChange={(e) => onChange?.(e.target.checked)}
          disabled={disabled}
          className="sr-only"
        />
        <span
          className={`
            pointer-events-none inline-block h-5 w-5 rounded-full border border-detec-ui-border bg-white shadow-sm
            absolute top-0.5 left-0.5 transition-transform
            ${checked ? 'translate-x-4 bg-detec-ui-accent border-detec-ui-accent' : ''}
          `}
        />
      </span>
      {label && <span className="text-sm text-detec-ui-text">{label}</span>}
    </label>
  );
}
