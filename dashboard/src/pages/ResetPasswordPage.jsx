import { useState } from 'react';
import DetecLogo from '../components/branding/DetecLogo';
import { forgotPassword } from '../lib/api';

export default function ResetPasswordPage({ onBack }) {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [token, setToken] = useState(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const result = await forgotPassword(email);
      setSubmitted(true);
      if (result.token) {
        setToken(result.token);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!token) return;
    try {
      const resetUrl = `${window.location.origin}/set-password?token=${token}&purpose=reset`;
      await navigator.clipboard.writeText(resetUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API not available
    }
  };

  return (
    <div className="min-h-screen bg-detec-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-3">
          <DetecLogo size="lg" className="justify-center" />
          <p className="text-sm text-detec-slate-400">Password Reset</p>
        </div>

        <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-6 space-y-4">
          {!submitted ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="text-lg font-semibold text-detec-slate-100 text-center">
                Forgot your password?
              </h2>
              <p className="text-sm text-detec-slate-400 text-center">
                Enter your email and we'll create a reset link.
              </p>

              {error && (
                <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-3 py-2 text-sm text-detec-enforce-block">
                  {error}
                </div>
              )}

              <label className="block space-y-1.5">
                <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
                />
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="w-full px-4 py-2.5 bg-detec-primary-500 hover:bg-detec-primary-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
              >
                {submitting ? 'Please wait...' : 'Send reset link'}
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="text-center">
                <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-900/30 mb-3">
                  <svg className="h-6 w-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-detec-slate-100">Check your email</h2>
                <p className="text-sm text-detec-slate-400 mt-1">
                  If that email is registered, a reset link has been created.
                </p>
              </div>

              {token && (
                <div className="space-y-2">
                  <p className="text-xs text-detec-slate-500">
                    Reset link (until email delivery is configured):
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 rounded-lg bg-detec-slate-900 border border-detec-slate-700 px-3 py-2 text-xs text-detec-slate-300 break-all">
                      {`${window.location.origin}/set-password?token=${token}&purpose=reset`}
                    </code>
                    <button
                      onClick={handleCopy}
                      className="shrink-0 rounded-lg border border-detec-slate-700 px-3 py-2 text-xs text-detec-slate-400 hover:bg-detec-slate-800 transition-colors"
                    >
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <p className="text-center text-sm text-detec-slate-500">
          <button
            type="button"
            onClick={onBack}
            className="text-detec-primary-400 hover:text-detec-primary-300 transition-colors"
          >
            Back to sign in
          </button>
        </p>
      </div>
    </div>
  );
}
