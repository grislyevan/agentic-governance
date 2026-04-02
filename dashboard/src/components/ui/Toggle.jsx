/**
 * Shared toggle (checkbox-style switch). Dark EDR: no neon focus.
 */
export default function Toggle({ checked, onChange, disabled, label, className = '' }) {
  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer ${disabled ? 'opacity-60 cursor-not-allowed' : ''} ${className}`}>
      <span className="relative inline-flex h-6 w-10 flex-shrink-0 rounded-full border border-detec-slate-700 bg-detec-slate-800 transition-colors focus-within:ring-2 focus-within:ring-detec-primary-500/20 focus-within:border-detec-primary-500">
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
            ${checked ? 'translate-x-4 bg-detec-primary-500 border-detec-primary-500' : 'border-detec-slate-600 bg-detec-slate-600'}
          `}
        />
      </span>
      {label && <span className="text-sm text-detec-slate-100">{label}</span>}
    </label>
  );
}
