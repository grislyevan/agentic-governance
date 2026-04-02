import { useState, useEffect } from 'react';
import { fetchSsoStatus } from '../lib/api';
import useAuth from '../hooks/useAuth';

export default function AdminSsoPage() {
  const { user } = useAuth();
  const [ssoStatus, setSsoStatus] = useState(null);

  useEffect(() => {
    fetchSsoStatus()
      .then((data) => setSsoStatus(data))
      .catch(() => setSsoStatus({ configured: false }));
  }, []);

  if (user?.role !== 'owner') {
    return (
      <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 text-sm text-detec-ink-secondary">
        Only organization owners can view SSO status.
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6 w-full">
      <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-detec-ink-primary uppercase tracking-wider">
          SSO configuration
        </h2>
        <p className="text-xs text-detec-ink-secondary">
          SSO is configured via environment variables on the server. Set OIDC_ISSUER,
          OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, and OIDC_REDIRECT_URI so users can sign in
          with your identity provider.
        </p>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-detec-ink-secondary">Status:</span>
            {ssoStatus === null ? (
              <span className="text-xs text-detec-ink-secondary">Loading...</span>
            ) : ssoStatus.configured ? (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Configured
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-detec-ink-secondary">
                <span className="h-1.5 w-1.5 rounded-full bg-detec-slate-200" />
                Not configured
              </span>
            )}
          </div>
          {ssoStatus?.configured && ssoStatus.issuer && (
            <div className="text-xs text-detec-ink-secondary">
              OIDC issuer: <code className="break-all">{ssoStatus.issuer}</code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
