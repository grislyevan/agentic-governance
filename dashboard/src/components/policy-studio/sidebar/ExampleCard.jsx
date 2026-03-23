/**
 * Step-specific example or tip.
 */
export default function ExampleCard({ title, body }) {
  if (!title && !body) return null;
  return (
    <div className="rounded-detec border border-detec-ui-border bg-detec-slate-50/80 p-4 shadow-detec-sm">
      <h3 className="text-sm font-semibold text-detec-ui-text mb-2">{title || 'Example'}</h3>
      <p className="text-xs text-detec-ui-muted leading-relaxed">{body}</p>
    </div>
  );
}
