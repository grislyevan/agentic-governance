/**
 * Policy Studio Step 4: Rules. data = draft.rules (mode, templateId, simpleConditions, advancedJson).
 * draftBasics/draftSource/draftScope used for simple-mode sentence display.
 */

import { useState } from 'react';
import { Textarea } from '../../ui';
import { ENDPOINT_SOURCES } from '../sources';
import RuleTemplatePicker from '../rules/RuleTemplatePicker';

const DEFAULT_ADVANCED = { decision_state: 'warn', conditions: {}, precedence: 100 };

export default function RulesStep({ data, onChange, draftBasics, draftSource, draftScope }) {
  const rules = data || {};
  const mode = rules.mode || 'simple';
  const advancedJson = rules.advancedJson;
  const [advancedText, setAdvancedText] = useState(() =>
    typeof advancedJson === 'object' && advancedJson !== null
      ? JSON.stringify(advancedJson, null, 2)
      : JSON.stringify(DEFAULT_ADVANCED, null, 2)
  );

  const sourceId = draftSource?.connectors?.[0] ?? draftSource?.category ?? null;
  const sourceName = ENDPOINT_SOURCES.find((s) => s.id === sourceId)?.name ?? 'selected source';
  const scopeIds = draftScope?.assets ?? [];
  const outcome = draftBasics?.outcome ?? 'warn';

  const handleModeChange = (newMode) => {
    onChange({ mode: newMode });
    if (newMode === 'advanced') {
      try {
        const parsed = JSON.parse(advancedText);
        onChange({ mode: newMode, advancedJson: parsed });
      } catch {
        onChange({ mode: newMode, advancedJson: DEFAULT_ADVANCED });
      }
    }
  };

  const handleAdvancedChange = (text) => {
    setAdvancedText(text);
    try {
      const parsed = JSON.parse(text);
      onChange({ advancedJson: parsed });
    } catch {
      // leave previous advancedJson
    }
  };

  return (
    <div className="space-y-6">
      <RuleTemplatePicker
        selectedId={rules.templateId}
        onSelect={(id) => onChange({ templateId: id })}
      />
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm text-detec-ink-secondary">Build conditions in simple sentences or edit JSON in advanced mode.</p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleModeChange('simple')}
            className={`h-10 px-4 rounded-detec text-sm font-medium ${
              mode === 'simple'
                ? 'bg-detec-brand text-white'
                : 'bg-white border border-detec-ui-border text-detec-ink-secondary hover:text-detec-ink-primary'
            }`}
          >
            Simple mode
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('advanced')}
            className={`h-10 px-4 rounded-detec text-sm font-medium ${
              mode === 'advanced'
                ? 'bg-detec-brand text-white'
                : 'bg-white border border-detec-ui-border text-detec-ink-secondary hover:text-detec-ink-primary'
            }`}
          >
            Advanced mode
          </button>
        </div>
      </div>

      {mode === 'simple' && (
        <div className="rounded-detec border border-detec-ui-border bg-detec-slate-50 px-4 py-3 text-sm text-detec-ink-secondary">
          When source is <strong className="text-detec-ink-primary">{sourceName}</strong>
          {scopeIds.length ? (
            <> and scope includes {scopeIds.join(', ')}</>
          ) : null}
          , then action is <strong className="text-detec-ink-primary">{outcome}</strong>.
          <p className="mt-2 text-xs">Conditions are derived from Basics and Scope. Use Advanced mode to edit the full condition structure.</p>
        </div>
      )}

      {mode === 'advanced' && (
        <div>
          <label className="block text-sm font-medium text-detec-ink-primary mb-1">Parameters (JSON)</label>
          <p className="text-xs text-detec-ink-secondary mb-2">Edit decision_state, conditions, precedence. Must be valid JSON. Advanced mode is for complex rule definitions.</p>
          <Textarea
            value={advancedText}
            onChange={(e) => handleAdvancedChange(e.target.value)}
            rows={12}
            spellCheck={false}
            className="font-mono"
          />
        </div>
      )}
    </div>
  );
}
