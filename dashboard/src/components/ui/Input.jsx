/**
 * Shared text input. Dark EDR spec: 40px height, 10px radius, slate-700 border, subtle indigo focus ring.
 */
export default function Input({ className = '', error, ...props }) {
  return (
    <input
      className={`
        w-full h-10 rounded-detec border bg-detec-slate-800 px-3 text-sm text-detec-slate-100
        placeholder:text-detec-slate-500
        focus:outline-none focus:ring-2 focus:ring-detec-primary-500/20 focus:border-detec-primary-500
        disabled:opacity-60 disabled:cursor-not-allowed
        ${error ? 'border-red-500 focus:ring-red-500/20 focus:border-red-500' : 'border-detec-slate-700'}
        ${className}
      `}
      {...props}
    />
  );
}
