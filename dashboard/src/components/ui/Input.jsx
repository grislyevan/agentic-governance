/**
 * Shared text input. Dark EDR spec: 40px height, 10px radius, slate-700 border, subtle indigo focus ring.
 */
export default function Input({ className = '', error, ...props }) {
  return (
    <input
      className={`
        w-full h-10 rounded-detec border bg-detec-surface px-3 text-sm text-detec-ink-primary
        placeholder:text-detec-ink-tertiary
        focus:outline-none focus:ring-2 focus:ring-detec-brand/20 focus:border-detec-brand
        disabled:opacity-60 disabled:cursor-not-allowed
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-edge'}
        ${className}
      `}
      {...props}
    />
  );
}
