/**
 * Shared buttons. Primary = blue fill, Secondary = outline, Tertiary = text/minimal. 40px height, 16px horizontal padding. No glowing focus.
 */
export default function Button({
  variant = 'primary',
  type = 'button',
  className = '',
  disabled,
  children,
  ...props
}) {
  const base = 'inline-flex items-center justify-center gap-2 h-10 px-4 font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-detec-ui-accent/20 focus:ring-offset-0 rounded-detec disabled:opacity-60 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-detec-ui-accent text-white hover:bg-detec-ui-accentHover border border-transparent',
    secondary: 'bg-white border border-detec-ui-border text-detec-ui-text hover:bg-detec-slate-50',
    tertiary: 'bg-transparent text-detec-ui-muted hover:text-detec-ui-text',
  };
  return (
    <button
      type={type}
      disabled={disabled}
      className={`${base} ${variants[variant] || variants.primary} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
