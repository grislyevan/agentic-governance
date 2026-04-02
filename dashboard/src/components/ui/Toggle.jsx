/**
 * Shared toggle (checkbox-style switch). Dark EDR: no neon focus.
 */
export default function Toggle({ checked, onChange, disabled, label, className = '' }) {
  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer ${disabled ? 'opacity-60 cursor-not-allowed' : ''} ${className}`}>
      <span className="relative inline-flex h-6 w-10 flex-shrink-0 rounded-full border border-detec-edge bg-detec-surface transition-colors focus-within:ring-2 focus-within:ring-detec-brand/20 focus-within:border-detec-brand">
        <input
          type="checkbox"
          checked={!!checked}
          onChange={(e) => onChange?.(e.target.checked)}
          disabled={disabled}
          className="sr-only"
        />
        <span
          className={`
            pointer-events-none inline-block h-5 w-5 rounded-full border
            absolute top-0.5 left-0.5 transition-transform
            ${checked ? 'translate-x-4 bg-detec-brand border-detec-brand' : 'border-detec-edge-emphasis bg-detec-edge-emphasis'}
          `}
        />
      </span>
      {label && <span className="text-sm text-detec-ink-primary">{label}</span>}
    </label>
  );
}
