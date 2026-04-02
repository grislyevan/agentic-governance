/**
 * Shared buttons. Primary = indigo fill, Secondary = dark outline, Tertiary = text/minimal. 40px height, 16px horizontal padding. No glowing focus.
 */
export default function Button({
  variant = 'primary',
  type = 'button',
  className = '',
  disabled,
  children,
  ...props
}) {
  const base = 'inline-flex items-center justify-center gap-2 h-10 px-4 font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-detec-brand/20 focus:ring-offset-0 rounded-detec disabled:opacity-60 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-detec-brand text-white hover:bg-detec-brand-hover border border-transparent',
    secondary: 'bg-detec-surface border border-detec-edge text-detec-ink-primary hover:bg-detec-raised',
    tertiary: 'bg-transparent text-detec-ink-secondary hover:text-detec-ink-primary',
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
