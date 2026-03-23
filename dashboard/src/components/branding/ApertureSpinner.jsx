/**
 * Animated aperture mark used as a loading indicator.
 * Uses the master PNG mark (from branding/Icon.icns) with CSS rotation.
 * Respects prefers-reduced-motion by falling back to a gentle pulse.
 */

const SIZE_MAP = { sm: 20, md: 28, lg: 40, xl: 56 };

export default function ApertureSpinner({ size = 'md', label = 'Loading', className = '' }) {
  const px = SIZE_MAP[size] || SIZE_MAP.md;

  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <img
        src="/mark-64.png"
        width={px}
        height={px}
        alt=""
        aria-hidden="true"
        className="detec-aperture-spin"
        draggable={false}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
