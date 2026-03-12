import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import { ssoCallback } from '../lib/api';
import { storeTokens } from '../lib/auth';
import DetecLogo from '../components/branding/DetecLogo';
import ApertureSpinner from '../components/branding/ApertureSpinner';

export default function SsoCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [error, setError] = useState(null);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !state) {
      setError('Missing authorization code or state. Please try signing in again.');
      return;
    }

    let cancelled = false;

    ssoCallback(code, state)
      .then((data) => {
        if (cancelled) return;
        storeTokens(data);
        refresh();
        navigate('/endpoints', { replace: true });
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'SSO sign-in failed. Please try again.');
      });

    return () => { cancelled = true; };
  }, [searchParams, navigate, refresh]);

  if (error) {
    return (
      <div className="min-h-screen bg-detec-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-6 text-center">
          <DetecLogo size="lg" className="justify-center" />
          <div className="rounded-xl border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
            {error}
          </div>
          <button
            type="button"
            onClick={() => navigate('/', { replace: true })}
            className="text-sm text-detec-primary-400 hover:text-detec-primary-300 transition-colors"
          >
            Return to sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-detec-slate-900 flex flex-col items-center justify-center gap-3">
      <ApertureSpinner size="xl" label="Completing sign in" />
      <span className="text-sm text-detec-slate-500">Signing you in...</span>
    </div>
  );
}
