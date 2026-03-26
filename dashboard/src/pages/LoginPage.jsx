import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import DetecLogo from '../components/branding/DetecLogo';
import ResetPasswordPage from './ResetPasswordPage';
import { fetchSsoStatus } from '../lib/api';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [ssoAvailable, setSsoAvailable] = useState(false);

  useEffect(() => {
    fetchSsoStatus()
      .then((data) => setSsoAvailable(data?.configured === true))
      .catch(() => {});
  }, []);

  if (mode === 'forgot') {
    return <ResetPasswordPage onBack={() => setMode('login')} />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'login') {
        const result = await login(email, password);
        if (result?.tokens?.password_reset_required) {
          navigate('/set-password?purpose=reset');
          return;
        }
      } else {
        await register(email, password, firstName, lastName, tenantName);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-detec-ui-page flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-3">
          <DetecLogo size="lg" className="justify-center" />
          <p className="text-sm text-detec-ui-muted">Agentic AI Governance</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="rounded-xl border border-detec-ui-border/50 bg-detec-ui-surface/80 p-6 space-y-4">
            <h2 className="text-lg font-semibold text-detec-ui-text text-center">
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h2>

            {error && (
              <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-3 py-2 text-sm text-detec-enforce-block">
                {error}
              </div>
            )}

            {mode === 'register' && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">First name</span>
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="Jane"
                      className="w-full bg-detec-ui-page border border-detec-ui-border rounded-lg px-3 py-2 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 transition-colors"
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Last name</span>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Smith"
                      className="w-full bg-detec-ui-page border border-detec-ui-border rounded-lg px-3 py-2 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 transition-colors"
                    />
                  </label>
                </div>
                <label className="block space-y-1.5">
                  <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Organization</span>
                  <input
                    type="text"
                    value={tenantName}
                    onChange={(e) => setTenantName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full bg-detec-ui-page border border-detec-ui-border rounded-lg px-3 py-2 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 transition-colors"
                  />
                </label>
              </>
            )}

            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Username</span>
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Administrator"
                required
                className="w-full bg-detec-ui-page border border-detec-ui-border rounded-lg px-3 py-2 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 transition-colors"
              />
            </label>

            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-detec-ui-muted uppercase tracking-wider">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                required
                minLength={8}
                className="w-full bg-detec-ui-page border border-detec-ui-border rounded-lg px-3 py-2 text-sm text-detec-ui-text placeholder:text-detec-ui-muted focus:outline-none focus:border-detec-ui-accent/50 transition-colors"
              />
            </label>

            <button
              type="submit"
              disabled={submitting}
              className="w-full px-4 py-2.5 bg-detec-ui-accent hover:bg-detec-ui-accent disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {submitting ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>

            {mode === 'login' && (
              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setMode('forgot')}
                  className="text-xs text-detec-ui-muted hover:text-detec-ui-accent transition-colors"
                >
                  Forgot password?
                </button>
              </div>
            )}

            {ssoAvailable && mode === 'login' && (
              <>
                <div className="flex items-center gap-3">
                  <div className="flex-1 border-t border-detec-ui-border" />
                  <span className="text-xs text-detec-ui-muted uppercase tracking-wider">or</span>
                  <div className="flex-1 border-t border-detec-ui-border" />
                </div>
                <a
                  href="/api/auth/sso/login"
                  className="block w-full px-4 py-2.5 border border-detec-ui-border hover:border-detec-ui-accent/50 text-detec-ui-text text-sm font-medium rounded-lg transition-colors text-center"
                >
                  Sign in with SSO
                </a>
              </>
            )}
          </div>

          <p className="text-center text-sm text-detec-ui-muted">
            {mode === 'login' ? (
              <>
                No account?{' '}
                <button type="button" onClick={() => { setMode('register'); setError(''); }} className="text-detec-ui-accent hover:text-detec-ui-accent transition-colors">
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" onClick={() => { setMode('login'); setError(''); }} className="text-detec-ui-accent hover:text-detec-ui-accent transition-colors">
                  Sign in
                </button>
              </>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}
