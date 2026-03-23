/**
 * Policy Studio state model: draftToApiPayload and validateStep.
 */
import { describe, it, expect } from 'vitest';
import { INITIAL_DRAFT, draftToApiPayload, validateStep } from './policyStudioState';

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
});
