/**
 * Step-specific example or tip.
 */
export default function ExampleCard({ title, body }) {
  if (!title && !body) return null;
  return (
    <div className="rounded-detec border border-detec-ui-border bg-detec-slate-50/80 p-4">
      <h3 className="text-sm font-semibold text-detec-ink-primary mb-2">{title || 'Example'}</h3>
      <p className="text-xs text-detec-ink-secondary leading-relaxed">{body}</p>
    </div>
  );
}
