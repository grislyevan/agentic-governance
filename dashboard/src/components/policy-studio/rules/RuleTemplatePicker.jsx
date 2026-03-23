/**
 * Intent template cards for the Rules step. Selecting one can guide the rule (v1: display only or set outcome/source).
 */
const INTENT_TEMPLATES = [
  { id: 'secrets', title: 'Prevent secrets from being exposed', description: 'Block or warn when credentials or API keys are at risk.' },
  { id: 'public_repo', title: 'Detect code pushed to public repos', description: 'Alert when code is pushed to public repositories.' },
  { id: 'sensitive_access', title: 'Alert on sensitive file access', description: 'Warn when sensitive or protected files are accessed.' },
  { id: 'outbound', title: 'Detect suspicious outbound transfers', description: 'Monitor or block unexpected outbound data transfers.' },
  { id: 'approval', title: 'Require approval before modifying protected resources', description: 'Require approval for changes to critical paths or assets.' },
];

export default function RuleTemplatePicker({ selectedId, onSelect }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-detec-ui-text">Intent template</p>
      <div className="flex flex-wrap gap-2">
        {INTENT_TEMPLATES.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onSelect(selectedId === t.id ? null : t.id)}
            className={`text-left rounded-detec border p-3 min-h-[84px] w-full sm:w-[280px] transition-colors ${
              selectedId === t.id
                ? 'border-detec-ui-accent bg-detec-ui-accent/5'
                : 'border-detec-ui-border bg-white hover:border-detec-slate-300'
            }`}
          >
            <div className="text-sm font-medium text-detec-ui-text">{t.title}</div>
            <div className="text-xs text-detec-ui-muted mt-0.5">{t.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
