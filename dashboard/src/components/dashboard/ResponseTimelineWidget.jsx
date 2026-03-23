import { useState, useEffect } from 'react';
import { fetchAuditLog } from '../../lib/api';

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
      <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 p-4">
        <h3 className="text-sm font-semibold text-detec-ui-text mb-2">Recent auto-responses</h3>
        <p className="text-xs text-detec-ui-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-detec-ui-text">Recent auto-responses</h3>
        {items.length > 0 && (
          <button
            type="button"
            onClick={() => onNavigate?.('playbooks')}
            className="text-xs text-detec-ui-accent hover:text-detec-ui-accent"
          >
            View all
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-detec-ui-muted">No playbook responses yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 5).map((entry) => (
            <li key={entry.id} className="text-xs text-detec-ui-muted">
              <span className="text-detec-ui-muted">{entry.occurred_at}</span>
              {' '}
              <span className="text-detec-ui-text">{entry.resource_id}</span>
              {entry.detail?.event_id && (
                <span className="text-detec-ui-muted"> ({entry.detail.event_id})</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
