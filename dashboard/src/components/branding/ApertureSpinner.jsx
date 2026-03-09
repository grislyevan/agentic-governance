/**
 * Animated aperture mark used as a loading indicator.
 * The three iris blades rotate slowly, evoking a lens focusing.
 * Respects prefers-reduced-motion by falling back to a gentle pulse.
 */

const TEAL = '#14b8a6';
const AMBER = '#f59e0b';
const INDIGO = '#6366f1';

const SIZE_MAP = { sm: 20, md: 28, lg: 40, xl: 56 };

export default function ApertureSpinner({ size = 'md', label = 'Loading', className = '' }) {
  const px = SIZE_MAP[size] || SIZE_MAP.md;

  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <svg
        width={px}
        height={px}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="detec-aperture-spin"
        aria-hidden="true"
      >
        <defs>
          <clipPath id={`asp-clip-${px}`}>
            <circle cx="50" cy="50" r="44" />
          </clipPath>
        </defs>

        <g clipPath={`url(#asp-clip-${px})`}>
          <path d="M18 14C28 6,46 4,56 10C62 14,58 22,50 28C42 34,36 42,38 48L46 50C44 44,44 36,50 30C56 24,50 16,40 14C34 13,26 16,18 14Z" fill={TEAL} />
          <path d="M10 28C6 40,8 18,18 14C26 16,34 13,40 14C50 16,56 24,50 30C44 36,44 44,46 50L38 48C36 42,30 36,22 34C14 32,10 32,10 28Z" fill={TEAL} opacity="0.85" />

          <path d="M80 18C90 28,94 46,88 58C84 66,76 62,70 54C64 46,56 42,52 44L50 46C54 44,62 44,68 50C74 56,78 52,80 44C82 36,80 28,80 18Z" fill={AMBER} />
          <path d="M68 8C78 10,88 16,80 18C80 28,82 36,80 44C78 52,74 56,68 50C62 44,54 44,50 46L52 44C56 42,62 38,66 30C70 22,70 14,68 8Z" fill={AMBER} opacity="0.85" />

          <path d="M30 90C18 82,10 66,14 54C16 46,26 48,34 52C42 56,48 50,48 46L50 48C48 52,42 56,36 54C28 52,24 56,26 64C28 72,32 82,30 90Z" fill={INDIGO} />
          <path d="M50 94C38 94,24 90,30 90C32 82,28 72,26 64C24 56,28 52,36 54C42 56,48 52,50 48L48 46C48 50,52 58,44 64C38 70,42 82,50 94Z" fill={INDIGO} opacity="0.85" />
        </g>

        <circle cx="50" cy="50" r="4.5" fill={INDIGO} />
        <circle cx="50" cy="50" r="2.5" fill="#f1f5f9" opacity="0.85" />
      </svg>
      <span className="sr-only">{label}</span>
    </span>
  );
}
