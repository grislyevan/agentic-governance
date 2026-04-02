/**
 * Contextual help for the current step.
 */
export default function HelpCard({ title, body }) {
  return (
    <div className="rounded-detec border border-detec-ui-border bg-detec-surface p-4">
      <h3 className="text-sm font-semibold text-detec-ink-primary mb-2">{title}</h3>
      <p className="text-xs text-detec-ink-secondary leading-relaxed">{body}</p>
    </div>
  );
}
