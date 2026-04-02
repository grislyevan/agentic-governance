import { useState, useEffect } from 'react';
import { fetchAuditLog } from '../../lib/api';

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return iso;
  }
}

export default function ResponseTimelineWidget({ onNavigate }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchAuditLog({ page: 1, pageSize: 5, action: 'playbook' })
      .then((data) => {
        if (!cancelled) setItems(data.items || []);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
        <h3 className="text-sm font-semibold text-detec-ink-primary mb-2">Recent auto-responses</h3>
        <p className="text-xs text-detec-ink-secondary">Loading…</p>
      </div>
    );
  }

  return (
    <div className="rounded-detec-md border border-detec-edge bg-detec-surface p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-detec-ink-primary">Recent auto-responses</h3>
        {items.length > 0 && (
          <button
            type="button"
            onClick={() => onNavigate?.('playbooks')}
            className="text-xs text-detec-brand hover:text-detec-brand"
          >
            View all
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-detec-ink-secondary">No playbook responses yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 5).map((entry) => {
            const action = entry.detail?.action || entry.action || 'Enforcement applied';
            const endpoint = entry.detail?.endpoint_name || entry.resource_id || 'unknown endpoint';
            const time = formatTime(entry.occurred_at);
            return (
              <li key={entry.id} className="text-xs text-detec-ink-primary leading-relaxed">
                <span className="font-medium">{action}</span>
                {' on '}
                <span className="font-medium">{endpoint}</span>
                <span className="text-detec-ink-secondary"> — {time}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
