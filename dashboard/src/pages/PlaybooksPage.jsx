import { useState, useEffect, useCallback } from 'react';
import useAuth from '../hooks/useAuth';
import {
  fetchPlaybooks,
  testPlaybook,
  fetchAuditLog,
} from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';

const SAMPLE_EVENT = {
  event_id: 'test-1',
  event_type: 'detection',
  event_version: '1.0',
  observed_at: new Date().toISOString(),
  tool: { name: 'Cursor', class: 'A' },
  policy: { decision_state: 'block', rule_id: 'ENFORCE-004' },
  severity: { level: 'P2' },
};

export default function PlaybooksPage({ onNavigate }) {
  const { user } = useAuth();
  const [playbooks, setPlaybooks] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState(null);

  const canManage = user?.role === 'owner' || user?.role === 'admin';

  const loadPlaybooks = useCallback(async () => {
    try {
      const data = await fetchPlaybooks();
      setPlaybooks(data.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTimeline = useCallback(async () => {
    try {
      const data = await fetchAuditLog({ page: 1, pageSize: 20, action: 'playbook' });
      setTimeline(data.items || []);
    } catch {
      setTimeline([]);
    }
  }, []);

  useEffect(() => {
    loadPlaybooks();
    loadTimeline();
  }, [loadPlaybooks, loadTimeline]);

  const handleTest = async (playbookId) => {
    setTestingId(playbookId);
    setTestResult(null);
    try {
      const result = await testPlaybook(playbookId, SAMPLE_EVENT);
      setTestResult({ id: playbookId, ...result });
      loadTimeline();
    } catch (e) {
      setTestResult({ id: playbookId, error: e.message });
    } finally {
      setTestingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <ApertureSpinner size="lg" label="Loading playbooks" />
      </div>
    );
  }

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-xl sm:text-2xl font-bold text-detec-ui-text">
          Response Playbooks
        </h1>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <section>
        <h2 className="text-sm font-semibold text-detec-ui-text mb-3">Playbooks</h2>
        <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 overflow-hidden">
          <ul className="divide-y divide-detec-slate-700/50">
            {playbooks.map((pb) => (
              <li key={pb.id} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-detec-ui-text">{pb.name}</div>
                  {pb.description && (
                    <div className="text-sm text-detec-ui-muted mt-0.5">{pb.description}</div>
                  )}
                  <div className="text-xs text-detec-ui-muted mt-1">
                    Trigger: {JSON.stringify(pb.trigger || {})}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {canManage && (
                    <button
                      type="button"
                      onClick={() => handleTest(pb.id)}
                      disabled={testingId === pb.id}
                      className="px-3 py-1.5 rounded-md text-sm font-medium bg-detec-ui-accent/15 text-detec-ui-accent hover:bg-detec-ui-accent/30 disabled:opacity-50"
                    >
                      {testingId === pb.id ? 'Testing…' : 'Dry run'}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {testResult && (
        <div className="rounded-lg border border-detec-ui-border bg-detec-ui-surface/80 p-4">
          <h3 className="text-sm font-medium text-detec-ui-text mb-2">Last test result</h3>
          {testResult.error ? (
            <p className="text-sm text-red-400">{testResult.error}</p>
          ) : (
            <pre className="text-xs text-detec-ui-text overflow-x-auto">
              {JSON.stringify({ matched: testResult.matched, actions_run: testResult.actions_run }, null, 2)}
            </pre>
          )}
        </div>
      )}

      <section>
        <h2 className="text-sm font-semibold text-detec-ui-text mb-3">Response timeline</h2>
        <p className="text-sm text-detec-ui-muted mb-2">
          Recent playbook responses (audit log).
        </p>
        <div className="rounded-lg border border-detec-ui-border/50 bg-detec-slate-50 overflow-hidden">
          {timeline.length === 0 ? (
            <div className="px-4 py-6 text-sm text-detec-ui-muted text-center">
              No playbook responses yet.
            </div>
          ) : (
            <ul className="divide-y divide-detec-slate-700/50">
              {timeline.map((entry) => (
                <li key={entry.id} className="px-4 py-2 text-sm">
                  <span className="text-detec-ui-muted">{entry.occurred_at}</span>
                  {' '}
                  <span className="text-detec-ui-text">{entry.action}</span>
                  {' '}
                  <span className="text-detec-ui-muted">playbook={entry.resource_id}</span>
                  {entry.detail?.event_id && (
                    <span className="text-detec-ui-muted"> event={entry.detail.event_id}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
