import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createApproval, createAllowListEntry } from '../../lib/api';

// ─── helpers ────────────────────────────────────────────────────────────────

function isoDateOffset(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10); // YYYY-MM-DD for date input
}

function isoDateToDatetime(dateStr) {
  // Append end-of-day UTC so the server gets a valid datetime
  return `${dateStr}T23:59:59Z`;
}

// ─── icons ───────────────────────────────────────────────────────────────────

function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

// ─── modal wrapper ────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} aria-hidden="true" />
      <div className="relative bg-detec-surface border border-detec-ui-border rounded-detec max-w-md w-full p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-detec-ink-primary">{title}</h3>
          <button type="button" onClick={onClose} className="text-detec-ink-secondary hover:text-detec-ink-primary" aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FieldLabel({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">{label}</span>
      {children}
    </label>
  );
}

const inputCls = 'w-full bg-detec-void border border-detec-ui-border rounded-detec px-3 py-2 text-sm text-detec-ink-primary placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/60';

// ─── Request Approval modal ───────────────────────────────────────────────────

function RequestApprovalModal({ prefill, onClose, onSuccess }) {
  const [toolName, setToolName] = useState(prefill.tool_name || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await createApproval({
        tool_name: toolName || undefined,
        confidence_band: prefill.confidence_band || undefined,
        confidence_score: prefill.confidence_score != null ? prefill.confidence_score : undefined,
        event_id: prefill.event_id || undefined,
        endpoint_id: prefill.endpoint_id || undefined,
      });
      onSuccess('Approval request created');
      onClose();
    } catch (e) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Request Approval" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <FieldLabel label="Tool name">
          <input
            type="text"
            value={toolName}
            onChange={e => setToolName(e.target.value)}
            className={inputCls}
            placeholder="Tool name"
          />
        </FieldLabel>
        <div className="grid grid-cols-2 gap-3">
          <FieldLabel label="Confidence band">
            <input type="text" readOnly value={prefill.confidence_band || '—'} className={`${inputCls} opacity-60 cursor-default`} />
          </FieldLabel>
          <FieldLabel label="Confidence score">
            <input
              type="text"
              readOnly
              value={prefill.confidence_score != null ? `${(prefill.confidence_score * 100).toFixed(0)}%` : '—'}
              className={`${inputCls} opacity-60 cursor-default`}
            />
          </FieldLabel>
        </div>
        {prefill.event_id && (
          <FieldLabel label="Event ID">
            <input type="text" readOnly value={prefill.event_id} className={`${inputCls} opacity-60 cursor-default font-mono text-xs`} />
          </FieldLabel>
        )}
        {error && (
          <p className="text-xs text-detec-enforce-block rounded bg-detec-enforce-block/10 border border-detec-enforce-block/30 px-3 py-2">{error}</p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-detec border border-detec-ui-border text-sm text-detec-ink-secondary hover:text-detec-ink-primary">
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-detec bg-amber-500/20 border border-amber-500/40 text-amber-400 text-sm font-medium hover:bg-amber-500/30 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Submitting…' : 'Submit'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ─── Add Temporary Exception modal ───────────────────────────────────────────

function AddExceptionModal({ prefill, onClose, onSuccess }) {
  const [pattern, setPattern] = useState(prefill.pattern || '');
  const [reasonCode, setReasonCode] = useState('');
  const [expiresAt, setExpiresAt] = useState(isoDateOffset(7));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pattern.trim()) { setError('Pattern is required'); return; }
    if (!reasonCode.trim()) { setError('Reason code is required'); return; }
    setError(null);
    setLoading(true);
    try {
      await createAllowListEntry({
        pattern: pattern.trim(),
        pattern_type: 'name',
        scope: 'tenant',
        reason_code: reasonCode.trim(),
        expires_at: isoDateToDatetime(expiresAt),
      });
      onSuccess(`Exception added, expires ${expiresAt}`);
      onClose();
    } catch (e) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Add Temporary Exception" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <FieldLabel label="Process / pattern">
          <input
            type="text"
            value={pattern}
            onChange={e => setPattern(e.target.value)}
            className={inputCls}
            placeholder="e.g. claude_code"
            required
          />
        </FieldLabel>
        <div className="grid grid-cols-2 gap-3">
          <FieldLabel label="Pattern type">
            <input type="text" readOnly value="name" className={`${inputCls} opacity-60 cursor-default`} />
          </FieldLabel>
          <FieldLabel label="Scope">
            <input type="text" readOnly value="tenant" className={`${inputCls} opacity-60 cursor-default`} />
          </FieldLabel>
        </div>
        <FieldLabel label="Reason code">
          <input
            type="text"
            value={reasonCode}
            onChange={e => setReasonCode(e.target.value)}
            className={inputCls}
            placeholder="e.g. approved-pilot-tool"
            maxLength={64}
            required
          />
        </FieldLabel>
        <FieldLabel label="Expires at">
          <input
            type="date"
            value={expiresAt}
            onChange={e => setExpiresAt(e.target.value)}
            className={inputCls}
            required
          />
        </FieldLabel>
        {error && (
          <p className="text-xs text-detec-enforce-block rounded bg-detec-enforce-block/10 border border-detec-enforce-block/30 px-3 py-2">{error}</p>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-detec border border-detec-ui-border text-sm text-detec-ink-secondary hover:text-detec-ink-primary">
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-detec bg-blue-500/20 border border-blue-500/40 text-blue-400 text-sm font-medium hover:bg-blue-500/30 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Saving…' : 'Add exception'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ─── TriageActions ────────────────────────────────────────────────────────────

/**
 * TriageActions — sticky SOC shortcut bar for SessionDetailPage.
 *
 * Props:
 *   report     — session report object (from fetchSessionReport)
 *   onToast    — ({ message, variant }) => void — called to show a toast
 */
export default function TriageActions({ report, onToast }) {
  const navigate = useNavigate();
  const [modal, setModal] = useState(null); // 'approval' | 'exception' | null

  if (!report) return null;

  // Derive pre-fill values from the report
  const timeline = report.session_timeline || [];
  const highestConfidenceEvent = timeline.reduce((best, e) => {
    if (e.confidence_score != null && (best == null || e.confidence_score > best.confidence_score)) return e;
    return best;
  }, null);

  const approvalPrefill = {
    tool_name: report.tool || '',
    confidence_band: report.session_confidence != null
      ? (report.session_confidence >= 0.8 ? 'high' : report.session_confidence >= 0.5 ? 'medium' : 'low')
      : undefined,
    confidence_score: report.session_confidence ?? undefined,
    event_id: highestConfidenceEvent?.event_id ?? undefined,
    endpoint_id: report.endpoint_id ?? undefined,
  };

  // Process name from first timeline entry that has one, or from report.tool
  const processName = (timeline.find(e => e.process_name)?.process_name) || report.tool || '';

  const exceptionPrefill = {
    pattern: processName,
  };

  const eventsHref = report.endpoint_id
    ? `/events?endpoint_id=${encodeURIComponent(report.endpoint_id)}`
    : '/events';

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 rounded-detec border border-detec-ui-border bg-detec-surface px-4 py-2.5">
        <span className="text-xs font-semibold text-detec-ink-secondary uppercase tracking-wider mr-1 hidden sm:inline">Triage</span>

        {/* Request Approval */}
        <button
          type="button"
          onClick={() => setModal('approval')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-detec bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/25 transition-colors"
        >
          <LockIcon />
          Request Approval
        </button>

        {/* Add Temporary Exception */}
        <button
          type="button"
          onClick={() => setModal('exception')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-detec bg-blue-500/15 border border-blue-500/30 text-blue-400 text-xs font-medium hover:bg-blue-500/25 transition-colors"
        >
          <ShieldIcon />
          Add Temporary Exception
        </button>

        {/* Related Events */}
        <button
          type="button"
          onClick={() => navigate(eventsHref)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-detec bg-detec-void border border-detec-ui-border text-detec-ink-secondary text-xs font-medium hover:text-detec-ink-primary hover:bg-detec-surface transition-colors"
        >
          <ListIcon />
          Related Events
        </button>
      </div>

      {modal === 'approval' && (
        <RequestApprovalModal
          prefill={approvalPrefill}
          onClose={() => setModal(null)}
          onSuccess={(msg) => { setModal(null); onToast?.({ message: msg, variant: 'success' }); }}
        />
      )}

      {modal === 'exception' && (
        <AddExceptionModal
          prefill={exceptionPrefill}
          onClose={() => setModal(null)}
          onSuccess={(msg) => { setModal(null); onToast?.({ message: msg, variant: 'success' }); }}
        />
      )}
    </>
  );
}
