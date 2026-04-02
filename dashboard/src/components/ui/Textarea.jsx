/**
 * Shared textarea. Dark EDR spec: min-height 96px, 10px radius, slate-700 border, subtle indigo focus ring.
 */
export default function Textarea({ className = '', error, ...props }) {
  return (
    <textarea
      className={`
        w-full min-h-[96px] rounded-detec border bg-detec-slate-800 px-3 py-2 text-sm text-detec-slate-100
        placeholder:text-detec-slate-500
        focus:outline-none focus:ring-2 focus:ring-detec-primary-500/20 focus:border-detec-primary-500
        disabled:opacity-60 disabled:cursor-not-allowed
        resize-y
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-slate-700'}
        ${className}
      `}
      {...props}
    />
  );
}
