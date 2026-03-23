/**
 * Shared text input. Light enterprise spec: 40px height, 10px radius, gray border, subtle blue focus ring.
 */
export default function Input({ className = '', error, ...props }) {
  return (
    <input
      className={`
        w-full h-10 rounded-detec border bg-white px-3 text-sm text-detec-ui-text
        placeholder:text-detec-ui-muted
        focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/20 focus:border-detec-ui-accent
        disabled:opacity-60 disabled:cursor-not-allowed
        shadow-detec-sm
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-ui-border'}
        ${className}
      `}
      {...props}
    />
  );
}
