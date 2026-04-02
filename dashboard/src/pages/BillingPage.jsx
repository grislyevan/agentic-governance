import { useState, useEffect, useCallback } from 'react';
import {
  fetchBillingStatus,
  fetchBillingTiers,
  createCheckoutSession,
  createPortalSession,
} from '../lib/api';

const TIER_LABELS = { free: 'Free', pro: 'Pro', enterprise: 'Enterprise' };
const TIER_COLORS = {
  free: 'bg-detec-slate-200 text-detec-ink-primary',
  pro: 'bg-detec-brand-muted text-detec-brand border border-detec-brand/30',
  enterprise: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
};
const STATUS_LABELS = {
  active: 'Active',
  trialing: 'Trial',
  past_due: 'Past Due',
  canceled: 'Canceled',
  paused: 'Paused',
};

export default function BillingPage() {
  const [billing, setBilling] = useState(null);
  const [tiers, setTiers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const load = useCallback(async () => {
    try {
      const [statusData, tiersData] = await Promise.all([
        fetchBillingStatus(),
        fetchBillingTiers(),
      ]);
      setBilling(statusData);
      setTiers(tiersData);
    } catch (err) {
      setError(err.message || 'Failed to load billing data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpgrade = async (tier) => {
    setActionLoading(tier);
    try {
      const { checkout_url } = await createCheckoutSession({
        tier,
        successUrl: `${window.location.origin}/billing?success=true`,
        cancelUrl: `${window.location.origin}/billing?canceled=true`,
      });
      window.location.href = checkout_url;
    } catch (err) {
      setError(err.message || 'Failed to create checkout session');
      setActionLoading(null);
    }
  };

  const handleManage = async () => {
    setActionLoading('portal');
    try {
      const { portal_url } = await createPortalSession({
        returnUrl: `${window.location.origin}/billing`,
      });
      window.location.href = portal_url;
    } catch (err) {
      setError(err.message || 'Failed to create portal session');
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-detec-brand border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-detec-md bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
        {error}
      </div>
    );
  }

  const currentTier = billing?.tier || 'free';
  const isStripeConfigured = billing?.stripe_configured;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold text-detec-ink-primary">Billing & Plan</h2>
        <p className="text-sm text-detec-ink-secondary mt-1">
          Manage your subscription and view usage limits.
        </p>
      </div>

      {/* Current Plan */}
      <div className="rounded-detec-md border border-detec-ui-border/50 bg-detec-surface/80 p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-base font-medium text-detec-ink-primary">Current Plan</h3>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${TIER_COLORS[currentTier]}`}>
                {TIER_LABELS[currentTier] || currentTier}
              </span>
              {billing?.status && billing.status !== 'active' && (
                <span className="px-2 py-0.5 rounded text-xs bg-amber-500/15 text-amber-400">
                  {STATUS_LABELS[billing.status] || billing.status}
                </span>
              )}
            </div>
            {billing?.is_trial && billing?.trial_ends_at && (
              <p className="text-sm text-amber-400 mt-1">
                Trial ends {new Date(billing.trial_ends_at).toLocaleDateString()}
              </p>
            )}
          </div>
          {isStripeConfigured && currentTier !== 'free' && (
            <button
              onClick={handleManage}
              disabled={actionLoading === 'portal'}
              className="px-4 py-2 rounded-detec-md text-sm font-medium text-detec-ink-primary bg-detec-slate-200 hover:bg-detec-slate-200 transition-colors disabled:opacity-50"
            >
              {actionLoading === 'portal' ? 'Loading...' : 'Manage Subscription'}
            </button>
          )}
        </div>

        {/* Usage Limits */}
        {billing?.limits && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
            <UsageStat
              label="Endpoints"
              value={billing.limits.max_endpoints ?? '∞'}
            />
            <UsageStat
              label="Events/Day"
              value={billing.limits.max_events_per_day != null ? billing.limits.max_events_per_day.toLocaleString() : '∞'}
            />
            <UsageStat
              label="Users"
              value={billing.limits.max_users ?? '∞'}
            />
            <UsageStat
              label="Retention"
              value={`${billing.limits.retention_days}d`}
            />
          </div>
        )}
      </div>

      {/* Tier Comparison */}
      {tiers && (
        <div>
          <h3 className="text-base font-medium text-detec-ink-primary mb-4">Available Plans</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(tiers).map(([tierName, limits]) => {
              const isCurrent = tierName === currentTier;
              const isUpgrade = tierOrder(tierName) > tierOrder(currentTier);
              return (
                <div
                  key={tierName}
                  className={`rounded-detec-md border p-5 ${
                    isCurrent
                      ? 'border-detec-brand/50 bg-detec-brand/5'
                      : 'border-detec-ui-border/50 bg-detec-surface/80'
                  }`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${TIER_COLORS[tierName]}`}>
                      {TIER_LABELS[tierName]}
                    </span>
                    {isCurrent && (
                      <span className="text-xs text-detec-brand">Current</span>
                    )}
                  </div>

                  <ul className="space-y-2 text-sm text-detec-ink-primary">
                    <LimitItem label="Endpoints" value={limits.max_endpoints} />
                    <LimitItem label="Events/day" value={limits.max_events_per_day} />
                    <LimitItem label="Users" value={limits.max_users} />
                    <LimitItem label="Retention" value={`${limits.retention_days} days`} />
                    <FeatureItem label="Webhooks" enabled={limits.webhook_enabled} />
                    <FeatureItem label="SSO/OIDC" enabled={limits.sso_enabled} />
                    <FeatureItem label="SIEM Export" enabled={limits.siem_export} />
                  </ul>

                  {isStripeConfigured && isUpgrade && limits.price_id && (
                    <button
                      onClick={() => handleUpgrade(tierName)}
                      disabled={!!actionLoading}
                      className="mt-4 w-full px-4 py-2 rounded-detec-md text-sm font-medium bg-detec-brand text-white hover:bg-detec-brand transition-colors disabled:opacity-50"
                    >
                      {actionLoading === tierName ? 'Loading...' : `Upgrade to ${TIER_LABELS[tierName]}`}
                    </button>
                  )}
                  {!isStripeConfigured && isUpgrade && (
                    <p className="mt-4 text-xs text-detec-ink-secondary text-center">
                      Contact sales to upgrade
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!isStripeConfigured && (
        <div className="rounded-detec-md bg-detec-surface/80 border border-detec-ui-border/50 p-4 text-sm text-detec-ink-secondary">
          Stripe billing is not configured. Set <code className="text-detec-ink-primary">STRIPE_SECRET_KEY</code> and{' '}
          <code className="text-detec-ink-primary">STRIPE_WEBHOOK_SECRET</code> to enable self-service upgrades.
        </div>
      )}
    </div>
  );
}

function UsageStat({ label, value }) {
  return (
    <div className="bg-detec-void/50 rounded-detec-md p-3 text-center">
      <div className="text-lg font-semibold text-detec-ink-primary">{value}</div>
      <div className="text-xs text-detec-ink-secondary mt-0.5">{label}</div>
    </div>
  );
}

function LimitItem({ label, value }) {
  const display = value == null ? '∞' : typeof value === 'number' ? value.toLocaleString() : value;
  return (
    <li className="flex justify-between">
      <span className="text-detec-ink-secondary">{label}</span>
      <span className="text-detec-ink-primary font-medium">{display}</span>
    </li>
  );
}

function FeatureItem({ label, enabled }) {
  return (
    <li className="flex justify-between">
      <span className="text-detec-ink-secondary">{label}</span>
      <span className={enabled ? 'text-green-400' : 'text-detec-ink-secondary'}>
        {enabled ? '✓' : '—'}
      </span>
    </li>
  );
}

function tierOrder(tier) {
  const order = { free: 0, pro: 1, enterprise: 2 };
  return order[tier] ?? 0;
}
