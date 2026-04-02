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
  const base = 'inline-flex items-center justify-center gap-2 h-10 px-4 font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-detec-primary-500/20 focus:ring-offset-0 rounded-detec disabled:opacity-60 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-detec-primary-500 text-white hover:bg-detec-primary-400 border border-transparent',
    secondary: 'bg-detec-slate-800 border border-detec-slate-700 text-detec-slate-100 hover:bg-detec-slate-700',
    tertiary: 'bg-transparent text-detec-slate-400 hover:text-detec-slate-100',
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
