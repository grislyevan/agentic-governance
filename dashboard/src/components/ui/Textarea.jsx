/**
 * Shared textarea. Light enterprise spec: min-height 96px, 10px radius, gray border, subtle blue focus ring.
 */
export default function Textarea({ className = '', error, ...props }) {
  return (
    <textarea
      className={`
        w-full min-h-[96px] rounded-detec border bg-white px-3 py-2 text-sm text-detec-ui-text
        placeholder:text-detec-ui-muted
        focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/20 focus:border-detec-ui-accent
        disabled:opacity-60 disabled:cursor-not-allowed
        shadow-detec-sm resize-y
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-ui-border'}
        ${className}
      `}
      {...props}
    />
  );
}
