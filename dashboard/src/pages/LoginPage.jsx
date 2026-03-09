import { useState } from 'react';
import useAuth from '../hooks/useAuth';
import DetecLogo from '../components/branding/DetecLogo';

export default function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
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
    <div className="min-h-screen bg-detec-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-3">
          <DetecLogo size="lg" className="justify-center" />
          <p className="text-sm text-detec-slate-400">Agentic AI Governance</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="rounded-xl border border-detec-slate-700/50 bg-detec-slate-800/50 p-6 space-y-4">
            <h2 className="text-lg font-semibold text-detec-slate-100 text-center">
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
                    <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">First name</span>
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="Jane"
                      className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">Last name</span>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Smith"
                      className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
                    />
                  </label>
                </div>
                <label className="block space-y-1.5">
                  <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">Organization</span>
                  <input
                    type="text"
                    value={tenantName}
                    onChange={(e) => setTenantName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
                  />
                </label>
              </>
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

            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-detec-slate-400 uppercase tracking-wider">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                required
                minLength={8}
                className="w-full bg-detec-slate-900 border border-detec-slate-700 rounded-lg px-3 py-2 text-sm text-detec-slate-200 placeholder:text-detec-slate-600 focus:outline-none focus:border-detec-primary-500/50 transition-colors"
              />
            </label>

            <button
              type="submit"
              disabled={submitting}
              className="w-full px-4 py-2.5 bg-detec-primary-500 hover:bg-detec-primary-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {submitting ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </div>

          <p className="text-center text-sm text-detec-slate-500">
            {mode === 'login' ? (
              <>
                No account?{' '}
                <button type="button" onClick={() => { setMode('register'); setError(''); }} className="text-detec-primary-400 hover:text-detec-primary-300 transition-colors">
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" onClick={() => { setMode('login'); setError(''); }} className="text-detec-primary-400 hover:text-detec-primary-300 transition-colors">
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
