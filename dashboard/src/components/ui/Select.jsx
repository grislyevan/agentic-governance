/**
 * Shared select. Light enterprise spec: 40px height, 10px radius, gray border, subtle blue focus ring.
 */
export default function Select({ className = '', error, children, ...props }) {
  return (
    <select
      className={`
        w-full h-10 rounded-detec border bg-white pl-3 pr-8 text-sm text-detec-ui-text
        focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/20 focus:border-detec-ui-accent
        disabled:opacity-60 disabled:cursor-not-allowed
        shadow-detec-sm appearance-none bg-[length:12px] bg-[right_12px_center] bg-no-repeat
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-ui-border'}
        ${className}
      `}
      style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'12\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%236b7280\' stroke-width=\'2\'%3E%3Cpath d=\'M6 9l6 6 6-6\'/%3E%3C/svg%3E")' }}
      {...props}
    >
      {children}
    </select>
  );
}
