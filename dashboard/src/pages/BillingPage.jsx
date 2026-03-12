import { useState, useEffect, useCallback } from 'react';
import {
  fetchBillingStatus,
  fetchBillingTiers,
  createCheckoutSession,
  createPortalSession,
} from '../lib/api';

const TIER_LABELS = { free: 'Free', pro: 'Pro', enterprise: 'Enterprise' };
const TIER_COLORS = {
  free: 'bg-detec-slate-700 text-detec-slate-300',
  pro: 'bg-detec-primary-500/20 text-detec-primary-400 border border-detec-primary-500/30',
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
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-detec-primary-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
        {error}
      </div>
    );
  }

  const currentTier = billing?.tier || 'free';
  const isStripeConfigured = billing?.stripe_configured;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold text-detec-slate-100">Billing & Plan</h2>
        <p className="text-sm text-detec-slate-400 mt-1">
          Manage your subscription and view usage limits.
        </p>
      </div>

      {/* Current Plan */}
      <div className="rounded-lg border border-detec-slate-700/50 bg-detec-slate-800/50 p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-base font-medium text-detec-slate-100">Current Plan</h3>
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
              className="px-4 py-2 rounded-lg text-sm font-medium text-detec-slate-300 bg-detec-slate-700 hover:bg-detec-slate-600 transition-colors disabled:opacity-50"
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
          <h3 className="text-base font-medium text-detec-slate-100 mb-4">Available Plans</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {Object.entries(tiers).map(([tierName, limits]) => {
              const isCurrent = tierName === currentTier;
              const isUpgrade = tierOrder(tierName) > tierOrder(currentTier);
              return (
                <div
                  key={tierName}
                  className={`rounded-lg border p-5 ${
                    isCurrent
                      ? 'border-detec-primary-500/50 bg-detec-primary-500/5'
                      : 'border-detec-slate-700/50 bg-detec-slate-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${TIER_COLORS[tierName]}`}>
                      {TIER_LABELS[tierName]}
                    </span>
                    {isCurrent && (
                      <span className="text-xs text-detec-primary-400">Current</span>
                    )}
                  </div>

                  <ul className="space-y-2 text-sm text-detec-slate-300">
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
                      className="mt-4 w-full px-4 py-2 rounded-lg text-sm font-medium bg-detec-primary-500 text-white hover:bg-detec-primary-600 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === tierName ? 'Loading...' : `Upgrade to ${TIER_LABELS[tierName]}`}
                    </button>
                  )}
                  {!isStripeConfigured && isUpgrade && (
                    <p className="mt-4 text-xs text-detec-slate-500 text-center">
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
        <div className="rounded-lg bg-detec-slate-800/50 border border-detec-slate-700/50 p-4 text-sm text-detec-slate-400">
          Stripe billing is not configured. Set <code className="text-detec-slate-300">STRIPE_SECRET_KEY</code> and{' '}
          <code className="text-detec-slate-300">STRIPE_WEBHOOK_SECRET</code> to enable self-service upgrades.
        </div>
      )}
    </div>
  );
}

function UsageStat({ label, value }) {
  return (
    <div className="bg-detec-slate-900/50 rounded-lg p-3 text-center">
      <div className="text-lg font-semibold text-detec-slate-100">{value}</div>
      <div className="text-xs text-detec-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function LimitItem({ label, value }) {
  const display = value == null ? '∞' : typeof value === 'number' ? value.toLocaleString() : value;
  return (
    <li className="flex justify-between">
      <span className="text-detec-slate-400">{label}</span>
      <span className="text-detec-slate-200 font-medium">{display}</span>
    </li>
  );
}

function FeatureItem({ label, enabled }) {
  return (
    <li className="flex justify-between">
      <span className="text-detec-slate-400">{label}</span>
      <span className={enabled ? 'text-green-400' : 'text-detec-slate-600'}>
        {enabled ? '✓' : '—'}
      </span>
    </li>
  );
}

function tierOrder(tier) {
  const order = { free: 0, pro: 1, enterprise: 2 };
  return order[tier] ?? 0;
}
