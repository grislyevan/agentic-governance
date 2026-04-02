/**
 * Shared textarea. Dark EDR spec: min-height 96px, 10px radius, slate-700 border, subtle indigo focus ring.
 */
export default function Textarea({ className = '', error, ...props }) {
  return (
    <textarea
      className={`
        w-full min-h-[96px] rounded-detec border bg-detec-surface px-3 py-2 text-sm text-detec-ink-primary
        placeholder:text-detec-ink-tertiary
        focus:outline-none focus:ring-2 focus:ring-detec-brand/20 focus:border-detec-brand
        disabled:opacity-60 disabled:cursor-not-allowed
        resize-y
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-edge'}
        ${className}
      `}
      {...props}
    />
  );
}
