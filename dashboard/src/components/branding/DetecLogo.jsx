/**
 * Detec aperture mark + wordmark.
 *
 * The mark is rendered from the master PNG extracted from branding/Icon.icns.
 * Color assignments per branding/logo-usage-guidelines.md.
 */

const WORDMARK_COLOR = '#2d2b7a';

const sizes = {
  sm: 28,
  md: 32,
  lg: 44,
};

function ApertureMark({ size = 32, className = '' }) {
  return (
    <img
      src="/mark-64.png"
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      className={`inline-block ${className}`}
      draggable={false}
    />
  );
}

export { ApertureMark };

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
