/**
 * Policy Studio state model: draftToApiPayload and validateStep.
 */
import { describe, it, expect } from 'vitest';
import { INITIAL_DRAFT, draftToApiPayload, apiPolicyToDraft, validateStep } from './policyStudioState';

describe('policyStudioState', () => {
  describe('draftToApiPayload', () => {
    it('produces rule_id from slugified basics.name', () => {
      const draft = {
        ...INITIAL_DRAFT,
        basics: { ...INITIAL_DRAFT.basics, name: 'Block secrets', severity: 'high', outcome: 'block' },
        source: { ...INITIAL_DRAFT.source, connectors: ['local_agent'] },
      };
      const out = draftToApiPayload(draft, false);
      expect(out.rule_id).toMatch(/^CUSTOM-/);
      expect(out.rule_id).toContain('BLOCK-SECRETS');
      expect(out.is_active).toBe(false);
    });

    it('sets is_active true when isPublish is true', () => {
      const draft = {
        ...INITIAL_DRAFT,
        basics: { ...INITIAL_DRAFT.basics, name: 'Test', severity: 'medium', outcome: 'warn' },
        source: { ...INITIAL_DRAFT.source, connectors: ['git'] },
      };
      expect(draftToApiPayload(draft, true).is_active).toBe(true);
    });

    it('maps source.connectors[0] to parameters.source_type', () => {
      const draft = {
        ...INITIAL_DRAFT,
        basics: { ...INITIAL_DRAFT.basics, name: 'X', severity: 'low', outcome: 'detect' },
        source: { ...INITIAL_DRAFT.source, connectors: ['network'] },
        scope: { ...INITIAL_DRAFT.scope, assets: ['source_code'] },
      };
      const out = draftToApiPayload(draft, false);
      expect(out.parameters.source_type).toBe('network');
      expect(out.parameters.scope).toEqual(['source_code']);
    });

    it('maps basics.whyThisMatters and recommendedResponse to parameters', () => {
      const draft = {
        ...INITIAL_DRAFT,
        basics: {
          ...INITIAL_DRAFT.basics,
          name: 'Y',
          severity: 'high',
          outcome: 'warn',
          whyThisMatters: 'Compliance',
          recommendedResponse: 'Review and escalate',
        },
        source: { ...INITIAL_DRAFT.source, category: 'local_agent' },
      };
      const out = draftToApiPayload(draft, false);
      expect(out.parameters.impact).toBe('Compliance');
      expect(out.parameters.remediation).toBe('Review and escalate');
    });
  });

  describe('validateStep', () => {
    it('basics: requires name, severity, outcome', () => {
      expect(validateStep('basics', INITIAL_DRAFT).length).toBeGreaterThan(0);
      const withName = {
        ...INITIAL_DRAFT,
        basics: { ...INITIAL_DRAFT.basics, name: 'A', severity: 'medium', outcome: 'warn' },
      };
      expect(validateStep('basics', withName)).toEqual([]);
    });

    it('source: requires connectors or category', () => {
      expect(validateStep('source', INITIAL_DRAFT).length).toBeGreaterThan(0);
      const withSource = {
        ...INITIAL_DRAFT,
        source: { ...INITIAL_DRAFT.source, connectors: ['git'] },
      };
      expect(validateStep('source', withSource)).toEqual([]);
    });

    it('scope and rules have no required validation', () => {
      expect(validateStep('scope', INITIAL_DRAFT)).toEqual([]);
      expect(validateStep('rules', INITIAL_DRAFT)).toEqual([]);
    });
  });

  describe('apiPolicyToDraft', () => {
    it('maps API policy back into draft shape', () => {
      const apiPolicy = {
        id: 'abc-123',
        rule_id: 'ENFORCE-001',
        rule_version: '0.4.0',
        description: 'Low confidence, read-only',
        is_active: true,
        is_baseline: true,
        category: 'enforcement',
        parameters: {
          decision_state: 'detect',
          severity: 'low',
          source_type: 'local_agent',
          scope: ['source_code', 'credentials'],
          goal: 'Detect low-risk reads',
          impact: 'Compliance baseline',
          remediation: 'Review weekly',
          conditions: {},
          precedence: 100,
        },
      };
      const draft = apiPolicyToDraft(apiPolicy);

      expect(draft.basics.name).toBe('ENFORCE-001');
      expect(draft.basics.description).toBe('Low confidence, read-only');
      expect(draft.basics.severity).toBe('low');
      expect(draft.basics.outcome).toBe('detect');
      expect(draft.basics.goal).toBe('Detect low-risk reads');
      expect(draft.basics.whyThisMatters).toBe('Compliance baseline');
      expect(draft.basics.recommendedResponse).toBe('Review weekly');
      expect(draft.basics.status).toBe('publish');

      expect(draft.source.connectors).toEqual(['local_agent']);
      expect(draft.source.category).toBe('local_agent');

      expect(draft.scope.assets).toEqual(['source_code', 'credentials']);

      // Simple mode because conditions is empty and precedence is 100
      expect(draft.rules.mode).toBe('simple');
    });

    it('selects advanced mode when conditions have entries', () => {
      const apiPolicy = {
        id: 'xyz-789',
        rule_id: 'CUSTOM-TEST',
        description: null,
        is_active: false,
        is_baseline: false,
        parameters: {
          decision_state: 'block',
          conditions: { tool_class: 'D' },
          precedence: 50,
        },
      };
      const draft = apiPolicyToDraft(apiPolicy);

      expect(draft.rules.mode).toBe('advanced');
      expect(draft.rules.advancedJson.conditions).toEqual({ tool_class: 'D' });
      expect(draft.rules.advancedJson.precedence).toBe(50);
      expect(draft.basics.status).toBe('draft');
    });

    it('round-trips: draftToApiPayload(apiPolicyToDraft(policy)) preserves key fields', () => {
      const apiPolicy = {
        id: 'rt-1',
        rule_id: 'CUSTOM-ROUNDTRIP',
        description: 'Round trip test',
        is_active: true,
        is_baseline: false,
        parameters: {
          decision_state: 'warn',
          severity: 'medium',
          source_type: 'git',
          scope: ['pii'],
          conditions: {},
          precedence: 100,
        },
      };

      const draft = apiPolicyToDraft(apiPolicy);
      const payload = draftToApiPayload(draft, true);

      // rule_id is re-slugified from basics.name which is the original rule_id
      expect(payload.rule_id).toMatch(/CUSTOM-/);
      expect(payload.is_active).toBe(true);
      expect(payload.parameters.decision_state).toBe('warn');
      expect(payload.parameters.source_type).toBe('git');
      expect(payload.parameters.scope).toEqual(['pii']);
    });

    it('handles missing parameters gracefully', () => {
      const apiPolicy = { id: 'empty', rule_id: 'X', is_active: false };
      const draft = apiPolicyToDraft(apiPolicy);
      expect(draft.basics.name).toBe('X');
      expect(draft.basics.severity).toBe('medium');
      expect(draft.source.connectors).toEqual([]);
      expect(draft.scope.assets).toEqual([]);
    });
  });
});
