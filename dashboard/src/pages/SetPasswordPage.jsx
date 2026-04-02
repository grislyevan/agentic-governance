import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import DetecLogo from '../components/branding/DetecLogo';
import { resetPassword, acceptInvite } from '../lib/api';

export default function SetPasswordPage({ onComplete }) {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const purpose = searchParams.get('purpose') || 'invite';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const isReset = purpose === 'reset';
  const title = isReset ? 'Set new password' : 'Activate your account';
  const subtitle = isReset
    ? 'Choose a new password for your account.'
    : 'Set a password to complete your account setup.';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setSubmitting(true);
    try {
      if (isReset) {
        await resetPassword(token, password);
      } else {
        await acceptInvite(token, password);
      }
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-detec-void flex items-center justify-center p-4">
        <div className="w-full max-w-sm text-center space-y-4">
          <DetecLogo size="lg" className="justify-center" />
          <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-6">
            <p className="text-sm text-detec-ink-secondary">
              Invalid or missing token. Please use the link from your invitation or reset email.
            </p>
          </div>
          {onComplete && (
            <button
              onClick={onComplete}
              className="text-sm text-detec-brand hover:text-detec-brand transition-colors"
            >
              Go to sign in
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-detec-void flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-3">
          <DetecLogo size="lg" className="justify-center" />
          <p className="text-sm text-detec-ink-secondary">Agentic AI Governance</p>
        </div>

        <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-6 space-y-4">
          {!success ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="text-lg font-semibold text-detec-ink-primary text-center">{title}</h2>
              <p className="text-sm text-detec-ink-secondary text-center">{subtitle}</p>

              {error && (
                <div className="rounded-detec-md border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-3 py-2 text-sm text-detec-enforce-block">
                  {error}
                </div>
              )}

              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">New password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  required
                  minLength={8}
                  className="w-full bg-detec-void border border-detec-ui-border rounded-detec-md px-3 py-2 text-sm text-detec-ink-primary placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/50 transition-colors"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-detec-ink-secondary uppercase tracking-wider">Confirm password</span>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Re-enter password"
                  required
                  minLength={8}
                  className="w-full bg-detec-void border border-detec-ui-border rounded-detec-md px-3 py-2 text-sm text-detec-ink-primary placeholder:text-detec-ink-secondary focus:outline-none focus:border-detec-brand/50 transition-colors"
                />
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="w-full px-4 py-2.5 bg-detec-brand hover:bg-detec-brand disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-detec-md transition-colors"
              >
                {submitting ? 'Please wait...' : isReset ? 'Reset password' : 'Activate account'}
              </button>
            </form>
          ) : (
            <div className="text-center space-y-3">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-900/30 mb-1">
                <svg className="h-6 w-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-detec-ink-primary">
                {isReset ? 'Password updated' : 'Account activated'}
              </h2>
              <p className="text-sm text-detec-ink-secondary">
                {isReset
                  ? 'Your password has been reset. You can now sign in.'
                  : 'Your account is ready. You can now sign in.'}
              </p>
              {onComplete && (
                <button
                  onClick={onComplete}
                  className="mt-2 px-4 py-2 bg-detec-brand hover:bg-detec-brand text-white text-sm font-medium rounded-detec-md transition-colors"
                >
                  Go to sign in
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
