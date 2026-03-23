/**
 * Policy Studio: guided policy creation flow (Basics → Source → Scope → Rules → Review).
 * Supports modal and full-page (asPage). Uses nested state model; compiles to current API (rule_id, description, is_active, parameters).
 */

import { useState, useCallback } from 'react';
import { createPolicy } from '../../lib/api';
import BasicsStep from './steps/BasicsStep';
import SourceStep from './steps/SourceStep';
import ScopeStep from './steps/ScopeStep';
import RulesStep from './steps/RulesStep';
import ReviewStep from './steps/ReviewStep';
import PolicyStudioSidebar from './PolicyStudioSidebar';
import { INITIAL_DRAFT, draftToApiPayload, validateStep } from './policyStudioState';

const STEPS = [
  { id: 'basics', label: 'Basics' },
  { id: 'source', label: 'Source' },
  { id: 'scope', label: 'Scope' },
  { id: 'rules', label: 'Rules' },
  { id: 'review', label: 'Review' },
];

export default function PolicyStudio({ onClose, onSaved, onError, asPage = false }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);

  const [draft, setDraft] = useState(INITIAL_DRAFT);

  const stepId = STEPS[stepIndex].id;
  const stepErrors = validateStep(stepId, draft);

  const canContinue = useCallback(() => {
    if (stepId === 'basics') return !!draft.basics?.name?.trim() && !!draft.basics?.severity && !!draft.basics?.outcome;
    if (stepId === 'source') return !!(draft.source?.connectors?.length || draft.source?.category);
    return true;
  }, [stepId, draft.basics, draft.source]);

  const handleNext = () => {
    setFormError(null);
    const errs = validateStep(stepId, draft);
    if (errs.length) {
      setFormError(errs[0]);
      return;
    }
    if (stepIndex < STEPS.length - 1) setStepIndex((i) => i + 1);
  };

  const handleBack = () => {
    setFormError(null);
    if (stepIndex > 0) setStepIndex((i) => i - 1);
  };

  const submit = async (isPublish) => {
    setFormError(null);
    const errs = [...validateStep('basics', draft), ...validateStep('source', draft)];
    if (errs.length) {
      setFormError(errs[0]);
      return;
    }
    setSaving(true);
    try {
      const payload = draftToApiPayload(draft, isPublish);
      await createPolicy(payload);
      onSaved();
    } catch (err) {
      setFormError(err.message);
      onError?.(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDraft = () => submit(false);
  const handlePublish = (isPublish) => submit(isPublish);
  const handlePreviewMatches = () => {
    setFormError('Preview matches is not available yet.');
  };

  const stepperRow = (
    <div className="flex items-center gap-2 px-5 py-0 h-16 rounded-detec-md border border-detec-ui-border bg-detec-ui-surface shadow-detec-sm">
      {STEPS.map((step, i) => (
        <span key={step.id} className="flex items-center gap-2">
          {i > 0 && <span className="w-6 h-px bg-detec-ui-border" aria-hidden />}
          <button
            type="button"
            onClick={() => setStepIndex(i)}
            className={`text-sm font-medium transition-colors ${
              i === stepIndex ? 'text-detec-ui-accent' : i < stepIndex ? 'text-detec-ui-text' : 'text-detec-ui-muted'
            }`}
          >
            {step.label}
          </button>
        </span>
      ))}
    </div>
  );

  const mainCardContent = (
    <div className="min-h-[560px] rounded-detec-md border border-detec-ui-border bg-detec-ui-surface shadow-detec-sm p-6 overflow-y-auto">
      {stepId === 'basics' && (
        <BasicsStep
          data={draft.basics}
          onChange={(next) => setDraft((prev) => ({ ...prev, basics: { ...prev.basics, ...next } }))}
        />
      )}
      {stepId === 'source' && (
        <SourceStep
          data={draft.source}
          onChange={(next) => setDraft((prev) => ({ ...prev, source: { ...prev.source, ...next } }))}
        />
      )}
      {stepId === 'scope' && (
        <ScopeStep
          data={draft.scope}
          onChange={(next) => setDraft((prev) => ({ ...prev, scope: { ...prev.scope, ...next } }))}
        />
      )}
      {stepId === 'rules' && (
        <RulesStep
          data={draft.rules}
          draftBasics={draft.basics}
          draftSource={draft.source}
          draftScope={draft.scope}
          onChange={(next) => setDraft((prev) => ({ ...prev, rules: { ...prev.rules, ...next } }))}
        />
      )}
      {stepId === 'review' && (
        <ReviewStep
          draft={draft}
          onSaveDraft={handleSaveDraft}
          onPublish={handlePublish}
          onPreviewMatches={handlePreviewMatches}
          saving={saving}
        />
      )}

      {formError && (
        <div className="mt-4 rounded-detec border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </div>
      )}

      {stepId !== 'review' && (
        <div className="flex justify-between gap-3 mt-6 pt-4 border-t border-detec-ui-border">
          <button
            type="button"
            onClick={stepIndex === 0 ? onClose : handleBack}
            className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm text-detec-ui-muted hover:bg-detec-slate-100"
          >
            {stepIndex === 0 ? 'Cancel' : 'Back'}
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={!canContinue()}
            className="h-10 px-4 rounded-detec bg-detec-ui-accent text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
          >
            Continue
          </button>
        </div>
      )}
    </div>
  );

  if (asPage) {
    return (
      <div className="flex flex-col gap-5 pb-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-detec-ui-text">New Policy</h1>
            <p className="text-sm text-detec-ui-muted mt-1">Create a policy in a few steps: basics, source, scope, rules, and review.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-slate-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveDraft}
              disabled={saving}
              className="h-10 px-4 rounded-detec bg-detec-ui-accent text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
            >
              Save draft
            </button>
          </div>
        </header>

        {stepperRow}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 min-h-0">
          <div className="min-w-0">{mainCardContent}</div>
          <div className="hidden lg:block min-w-0">
            <div className="rounded-detec-md border border-detec-ui-border bg-detec-ui-surface shadow-detec-sm p-4 overflow-y-auto">
              <PolicyStudioSidebar stepId={stepId} draft={draft} />
            </div>
          </div>
        </div>

        {stepId === 'review' && (
          <footer className="sticky bottom-0 border-t border-detec-ui-border bg-detec-ui-surface shadow-detec-sm py-4 px-6 flex justify-between items-center">
            <button type="button" onClick={onClose} className="h-10 px-4 rounded-detec text-sm text-detec-ui-muted hover:text-detec-ui-text">
              Cancel
            </button>
            <div className="flex gap-2">
              <button type="button" onClick={handlePreviewMatches} className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-slate-50">
                Preview matches
              </button>
              <button type="button" onClick={() => handlePublish(false)} disabled={saving} className="h-10 px-4 rounded-detec border border-detec-ui-border text-sm text-detec-ui-text hover:bg-detec-slate-50 disabled:opacity-50">
                Submit for review
              </button>
              <button type="button" onClick={() => handlePublish(true)} disabled={saving} className="h-10 px-4 rounded-detec bg-detec-ui-accent text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50">
                Publish
              </button>
            </div>
          </footer>
        )}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-detec-lg border border-detec-ui-border bg-detec-ui-surface shadow-detec-card overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-6 py-4 border-b border-detec-ui-border bg-detec-ui-surface shrink-0">
          {STEPS.map((step, i) => (
            <span key={step.id} className="flex items-center gap-2">
              {i > 0 && <span className="text-detec-ui-border">/</span>}
              <button
                type="button"
                onClick={() => setStepIndex(i)}
                className={`text-sm font-medium transition-colors ${
                  i === stepIndex ? 'text-detec-ui-accent' : i < stepIndex ? 'text-detec-ui-text' : 'text-detec-ui-muted'
                }`}
              >
                {step.label}
              </button>
            </span>
          ))}
        </div>

        <div className="flex flex-1 min-h-0">
          <div className="flex-1 overflow-y-auto p-6">
            {stepId === 'basics' && (
              <BasicsStep
                data={draft.basics}
                onChange={(next) => setDraft((prev) => ({ ...prev, basics: { ...prev.basics, ...next } }))}
              />
            )}
            {stepId === 'source' && (
              <SourceStep
                data={draft.source}
                onChange={(next) => setDraft((prev) => ({ ...prev, source: { ...prev.source, ...next } }))}
              />
            )}
            {stepId === 'scope' && (
              <ScopeStep
                data={draft.scope}
                onChange={(next) => setDraft((prev) => ({ ...prev, scope: { ...prev.scope, ...next } }))}
              />
            )}
            {stepId === 'rules' && (
              <RulesStep
                data={draft.rules}
                draftBasics={draft.basics}
                draftSource={draft.source}
                draftScope={draft.scope}
                onChange={(next) => setDraft((prev) => ({ ...prev, rules: { ...prev.rules, ...next } }))}
              />
            )}
            {stepId === 'review' && (
              <ReviewStep
                draft={draft}
                onSaveDraft={handleSaveDraft}
                onPublish={handlePublish}
                onPreviewMatches={handlePreviewMatches}
                saving={saving}
              />
            )}

            {formError && (
              <div className="mt-4 rounded-detec border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            )}

            {stepId !== 'review' && (
              <div className="flex justify-between gap-3 mt-6 pt-4 border-t border-detec-ui-border">
                <button
                  type="button"
                  onClick={stepIndex === 0 ? onClose : handleBack}
                  className="rounded-detec border border-detec-ui-border px-4 py-2 text-sm text-detec-ui-muted hover:bg-detec-slate-100"
                >
                  {stepIndex === 0 ? 'Cancel' : 'Back'}
                </button>
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={!canContinue()}
                  className="rounded-detec bg-detec-ui-accent px-4 py-2 text-sm font-medium text-white hover:bg-detec-ui-accentHover disabled:opacity-50"
                >
                  Continue
                </button>
              </div>
            )}
          </div>
          <div className="w-64 shrink-0 border-l border-detec-ui-border p-4 overflow-y-auto hidden sm:block">
            <PolicyStudioSidebar stepId={stepId} draft={draft} />
          </div>
        </div>
      </div>
    </div>
  );
}
