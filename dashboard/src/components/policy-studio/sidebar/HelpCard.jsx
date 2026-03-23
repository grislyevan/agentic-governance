/**
 * Contextual help for the current step.
 */
export default function HelpCard({ title, body }) {
  return (
    <div className="rounded-detec border border-detec-ui-border bg-detec-ui-surface p-4 shadow-detec-sm">
      <h3 className="text-sm font-semibold text-detec-ui-text mb-2">{title}</h3>
      <p className="text-xs text-detec-ui-muted leading-relaxed">{body}</p>
    </div>
  );
}
