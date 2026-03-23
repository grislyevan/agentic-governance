/**
 * Policy Studio state model (nested) and mapping to current API payload.
 * Spec: basics, source, scope, rules, review. Serializes to rule_id, rule_version, description, is_active, parameters.
 */

export const INITIAL_DRAFT = {
  basics: {
    name: '',
    description: '',
    goal: '',
    severity: 'medium',
    outcome: 'warn',
    whyThisMatters: '',
    recommendedResponse: '',
    status: 'draft',
  },
  source: {
    category: '',
    connectors: [],
    tags: [],
  },
  scope: {
    assets: [],
    subjects: [],
    sensitivity: [],
  },
  rules: {
    mode: 'simple',
    templateId: null,
    simpleConditions: [],
    advancedJson: {},
  },
  review: {
    previewEnabled: false,
  },
};

function slugify(name) {
  if (!name || !name.trim()) return 'CUSTOM-001';
  const base = name.trim().replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-]/g, '').toUpperCase().slice(0, 20);
  return base ? `CUSTOM-${base}` : 'CUSTOM-001';
}

/**
 * Map nested draft to current policy API payload. No backend change.
 * Draft => is_active: false; Publish => is_active: true.
 */
export function draftToApiPayload(draft, isPublish) {
  const { basics, source, scope, rules } = draft;
  const ruleId = slugify(basics?.name);
  const isActive = isPublish ?? (basics?.status !== 'draft');

  const sourceId = source?.connectors?.[0] ?? source?.category ?? null;
  const scopeIds = Array.isArray(scope?.assets) ? scope.assets : [];

  let parameters = {
    decision_state: basics?.outcome || 'warn',
    conditions: {},
    precedence: 100,
    goal: basics?.goal || undefined,
    severity: basics?.severity || undefined,
    impact: basics?.whyThisMatters || undefined,
    remediation: basics?.recommendedResponse || undefined,
    source_type: sourceId || undefined,
    scope: scopeIds,
  };

  if (rules?.mode === 'advanced' && rules?.advancedJson && Object.keys(rules.advancedJson).length > 0) {
    const j = rules.advancedJson;
    if (j.conditions) parameters.conditions = j.conditions;
    if (j.precedence != null) parameters.precedence = j.precedence;
    if (j.decision_state) parameters.decision_state = j.decision_state;
  }

  return {
    rule_id: ruleId,
    rule_version: '0.4.0',
    description: (basics?.description ?? '').trim() || null,
    is_active: isActive,
    parameters,
  };
}

/** Validation: required fields per step (for step-scoped errors). */
export function validateStep(stepId, draft) {
  if (stepId === 'basics') {
    const b = draft.basics;
    const errors = [];
    if (!b?.name?.trim()) errors.push('Policy name is required.');
    if (!b?.severity) errors.push('Severity is required.');
    if (!b?.outcome) errors.push('Outcome is required.');
    return errors;
  }
  if (stepId === 'source') {
    const c = draft.source?.connectors;
    if (!c?.length && !draft.source?.category) return ['Please select a source.'];
    return [];
  }
  return [];
}
