/**
 * Detec aperture mark + wordmark.
 *
 * The mark is a circular iris formed by three smooth, swooping blades
 * in teal, amber, and indigo that spiral inward toward a central dot.
 * Traced from detec-logo-concept-v2.png.
 * Color assignments per branding/logo-usage-guidelines.md.
 */

const TEAL = '#14b8a6';
const AMBER = '#f59e0b';
const INDIGO = '#6366f1';
const WORDMARK_COLOR = '#2d2b7a';

const sizes = {
  sm: 28,
  md: 32,
  lg: 44,
};

function ApertureMark({ size = 32, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <clipPath id="detec-iris-clip">
          <circle cx="50" cy="50" r="44" />
        </clipPath>
      </defs>

      <g clipPath="url(#detec-iris-clip)">
        {/* Teal blade — top-left, swoops clockwise from ~10 o'clock */}
        <path
          d="M18 14 C28 6, 46 4, 56 10 C62 14, 58 22, 50 28
             C42 34, 36 42, 38 48 L46 50
             C44 44, 44 36, 50 30 C56 24, 50 16, 40 14
             C34 13, 26 16, 18 14Z"
          fill={TEAL}
        />
        <path
          d="M10 28 C6 40, 8 18, 18 14 C26 16, 34 13, 40 14
             C50 16, 56 24, 50 30 C44 36, 44 44, 46 50
             L38 48 C36 42, 30 36, 22 34 C14 32, 10 32, 10 28Z"
          fill={TEAL}
          opacity="0.85"
        />

        {/* Amber blade — top-right, swoops clockwise from ~2 o'clock */}
        <path
          d="M80 18 C90 28, 94 46, 88 58 C84 66, 76 62, 70 54
             C64 46, 56 42, 52 44 L50 46
             C54 44, 62 44, 68 50 C74 56, 78 52, 80 44
             C82 36, 80 28, 80 18Z"
          fill={AMBER}
        />
        <path
          d="M68 8 C78 10, 88 16, 80 18 C80 28, 82 36, 80 44
             C78 52, 74 56, 68 50 C62 44, 54 44, 50 46
             L52 44 C56 42, 62 38, 66 30 C70 22, 70 14, 68 8Z"
          fill={AMBER}
          opacity="0.85"
        />

        {/* Indigo blade — bottom, swoops clockwise from ~6 o'clock */}
        <path
          d="M30 90 C18 82, 10 66, 14 54 C16 46, 26 48, 34 52
             C42 56, 48 50, 48 46 L50 48
             C48 52, 42 56, 36 54 C28 52, 24 56, 26 64
             C28 72, 32 82, 30 90Z"
          fill={INDIGO}
        />
        <path
          d="M50 94 C38 94, 24 90, 30 90 C32 82, 28 72, 26 64
             C24 56, 28 52, 36 54 C42 56, 48 52, 50 48
             L48 46 C48 50, 52 58, 44 64 C38 70, 42 82, 50 94Z"
          fill={INDIGO}
          opacity="0.85"
        />
      </g>

      {/* Central focal dot */}
      <circle cx="50" cy="50" r="4.5" fill={INDIGO} />
      <circle cx="50" cy="50" r="2.5" fill="#f1f5f9" opacity="0.85" />
    </svg>
  );
}

export default function DetecLogo({ size = 'md', markOnly = false, dark = true, className = '' }) {
  const px = sizes[size] || sizes.md;

  if (markOnly) {
    return <ApertureMark size={px} className={className} />;
  }

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <ApertureMark size={px} />
      <span
        className="font-sans font-bold tracking-tight"
        style={{
          fontSize: px * 0.55,
          color: dark ? '#f1f5f9' : WORDMARK_COLOR,
        }}
      >
        Detec
      </span>
    </span>
  );
}
