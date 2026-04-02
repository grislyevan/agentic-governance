/**
 * Policy Studio Step 1: Basics (name, description, goal, severity, outcome, whyThisMatters, recommendedResponse, status).
 * data = draft.basics; onChange(partial) merges into draft.basics.
 */

import { SEVERITY_OPTIONS } from '../sources';
import { Input, Select } from '../../ui';

const OUTCOME_LABELS = [
  { value: 'detect', label: 'Detect' },
  { value: 'warn', label: 'Warn' },
  { value: 'approval_required', label: 'Require approval' },
  { value: 'block', label: 'Block' },
];

export default function BasicsStep({ data, onChange }) {
  const b = data || {};

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Policy name</label>
        <p className="text-xs text-detec-ink-secondary mb-2">Give this policy a clear, searchable name.</p>
        <Input
          type="text"
          value={b.name || ''}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="e.g. Block high-risk tools on sensitive paths"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Short description</label>
        <p className="text-xs text-detec-ink-secondary mb-2">One line describing what this policy does.</p>
        <Input
          type="text"
          value={b.description || ''}
          onChange={(e) => onChange({ description: e.target.value })}
          placeholder="What this policy does"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Policy goal</label>
        <p className="text-xs text-detec-ink-secondary mb-2">What is this policy for?</p>
        <Input
          type="text"
          value={b.goal || ''}
          onChange={(e) => onChange({ goal: e.target.value })}
          placeholder="Optional"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-detec-ink-primary mb-1">Severity</label>
          <p className="text-xs text-detec-ink-secondary mb-2">How important is a match from this policy?</p>
          <Select
            value={b.severity || 'medium'}
            onChange={(e) => onChange({ severity: e.target.value })}
          >
            {SEVERITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </Select>
        </div>
        <div>
          <label className="block text-sm font-medium text-detec-ink-primary mb-1">Outcome</label>
          <p className="text-xs text-detec-ink-secondary mb-2">What should happen when the policy matches?</p>
          <Select
            value={b.outcome || 'warn'}
            onChange={(e) => onChange({ outcome: e.target.value })}
          >
            {OUTCOME_LABELS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </Select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Why this matters</label>
        <p className="text-xs text-detec-ink-secondary mb-2">Business or compliance reason.</p>
        <Input
          type="text"
          value={b.whyThisMatters || ''}
          onChange={(e) => onChange({ whyThisMatters: e.target.value })}
          placeholder="Optional"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Recommended response</label>
        <p className="text-xs text-detec-ink-secondary mb-2">What the operator should do when notified.</p>
        <Input
          type="text"
          value={b.recommendedResponse || ''}
          onChange={(e) => onChange({ recommendedResponse: e.target.value })}
          placeholder="Optional"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-detec-ink-primary mb-1">Status</label>
        <p className="text-xs text-detec-ink-secondary mb-2">Draft until you publish.</p>
        <Select
          value={b.status || 'draft'}
          onChange={(e) => onChange({ status: e.target.value })}
        >
          <option value="draft">Draft</option>
          <option value="publish">Publish</option>
        </Select>
      </div>
    </div>
  );
}
