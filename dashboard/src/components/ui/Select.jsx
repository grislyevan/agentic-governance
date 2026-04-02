/**
 * Shared select. Dark EDR spec: 40px height, 10px radius, slate-700 border, subtle indigo focus ring.
 */
export default function Select({ className = '', error, children, ...props }) {
  return (
    <select
      className={`
        w-full h-10 rounded-detec border bg-detec-surface pl-3 pr-8 text-sm text-detec-ink-primary
        focus:outline-none focus:ring-2 focus:ring-detec-brand/20 focus:border-detec-brand
        disabled:opacity-60 disabled:cursor-not-allowed
        appearance-none bg-[length:12px] bg-[right_12px_center] bg-no-repeat
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-edge'}
        ${className}
      `}
      style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'12\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%2394a3b8\' stroke-width=\'2\'%3E%3Cpath d=\'M6 9l6 6 6-6\'/%3E%3C/svg%3E")' }}
      {...props}
    >
      {children}
    </select>
  );
}
