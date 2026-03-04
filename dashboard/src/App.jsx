import { useState, useCallback } from 'react';
import { parseNdjson, buildEndpointSummary } from './parseNdjson';
import './App.css';

function useEvents() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [source, setSource] = useState(null);
  const [lastFile, setLastFile] = useState(null);

  const loadFromApi = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSource('api');
    setLastFile(null);
    try {
      const res = await fetch('/api/events', { cache: 'no-store' });
      if (!res.ok) throw new Error(
        res.status === 404
          ? 'No NDJSON file served. Start the API server or run the collector first.'
          : `Server returned ${res.status}`
      );
      const text = await res.text();
      setEvents(parseNdjson(text));
    } catch (e) {
      setError(e.message);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFromFile = useCallback((file) => {
    setError(null);
    setSource('file');
    setLastFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setEvents(parseNdjson(reader.result));
      } catch (e) {
        setError(e.message);
        setEvents([]);
      }
    };
    reader.onerror = () => setError('Failed to read file');
    reader.readAsText(file);
  }, []);

  const refresh = useCallback(() => {
    if (source === 'api') {
      setLoading(true);
      setError(null);
      fetch(`/api/events?_=${Date.now()}`, { cache: 'no-store' })
        .then((res) => {
          if (!res.ok) throw new Error(
            res.status === 404 ? 'No NDJSON file served.' : `Server returned ${res.status}`
          );
          return res.text();
        })
        .then((text) => setEvents(parseNdjson(text)))
        .catch((e) => {
          setError(e.message);
          setEvents([]);
        })
        .finally(() => setLoading(false));
    } else if (source === 'file' && lastFile) {
      setError(null);
      setLoading(true);
      const reader = new FileReader();
      reader.onload = () => {
        try { setEvents(parseNdjson(reader.result)); }
        catch (e) { setError(e.message); setEvents([]); }
        setLoading(false);
      };
      reader.onerror = () => { setError('Failed to read file'); setLoading(false); };
      reader.readAsText(lastFile);
    }
  }, [source, lastFile]);

  const canRefresh = events.length > 0 && (source === 'api' || lastFile);

  return { events, loading, error, loadFromApi, loadFromFile, refresh, canRefresh };
}

function EndpointHeader({ endpoint, lastObserved, eventCount }) {
  if (!endpoint) return null;
  return (
    <header className="endpoint-header">
      <div className="endpoint-id">{endpoint.id}</div>
      <div className="endpoint-meta">
        <span>{endpoint.os}</span>
        <span className="sep">·</span>
        <span className={`posture posture-${endpoint.posture}`}>{endpoint.posture}</span>
        {lastObserved && (
          <>
            <span className="sep">·</span>
            <span className="last-scan">Last scan: {new Date(lastObserved).toLocaleString()}</span>
          </>
        )}
        {eventCount != null && (
          <>
            <span className="sep">·</span>
            <span className="event-count">{eventCount} events</span>
          </>
        )}
      </div>
    </header>
  );
}

function SeverityBadge({ level }) {
  if (!level) return <span className="severity severity-none">—</span>;
  return <span className={`severity severity-${level.toLowerCase()}`}>{level}</span>;
}

function ToolRow({ tool }) {
  const [expanded, setExpanded] = useState(false);

  const decisionClass = {
    detect: 'decision-detect',
    warn: 'decision-warn',
    approval_required: 'decision-approval',
    block: 'decision-block',
  }[tool.decision_state] || '';

  const toolClassLabel = tool.class !== '—'
    ? <span className="tool-class-badge" title={toolClassDesc(tool.class)}>Class {tool.class}</span>
    : <span className="tool-class-badge">—</span>;

  return (
    <>
      <tr className={expanded ? 'row-expanded' : ''} onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
        <td className="tool-name">
          {tool.name}
          {tool.version && <span className="tool-version">{tool.version}</span>}
        </td>
        <td>{toolClassLabel}</td>
        <td>
          <span className={`confidence confidence-${(tool.confidenceBand || '').toLowerCase()}`}>
            {tool.confidenceBand}
          </span>
          {tool.attribution_confidence != null && (
            <span className="confidence-value"> ({Math.round(tool.attribution_confidence * 100)}%)</span>
          )}
        </td>
        <td>
          <span className={`decision ${decisionClass}`}>{tool.policyLabel}</span>
        </td>
        <td><SeverityBadge level={tool.severity_level} /></td>
        <td className="reason">
          {tool.summary || (tool.reason_codes?.length ? tool.reason_codes.slice(0, 2).join(', ') : '—')}
        </td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={6}>
            <div className="detail-panel">
              {tool.enforcement_applied && (
                <div className="detail-section">
                  <span className="detail-label">Enforcement applied:</span>
                  <span className={`decision decision-${tool.enforcement_applied}`}>
                    {tool.enforcement_applied.replace(/_/g, ' ')}
                  </span>
                </div>
              )}
              {tool.reason_codes?.length > 0 && (
                <div className="detail-section">
                  <span className="detail-label">Reason codes:</span>
                  <span className="detail-codes">{tool.reason_codes.join(' · ')}</span>
                </div>
              )}
              {tool.summary && (
                <div className="detail-section">
                  <span className="detail-label">Action summary:</span>
                  <span className="detail-summary">{tool.summary}</span>
                </div>
              )}
              {tool.observed_at && (
                <div className="detail-section">
                  <span className="detail-label">Observed:</span>
                  <span>{new Date(tool.observed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function toolClassDesc(cls) {
  const descs = {
    A: 'Class A — Assistive IDE Extension',
    B: 'Class B — Local Model Runtime',
    C: 'Class C — Autonomous Executor',
    D: 'Class D — Persistent Autonomous Agent',
  };
  return descs[cls] || `Class ${cls}`;
}

function SummaryBar({ tools }) {
  if (!tools.length) return null;
  const counts = { block: 0, approval_required: 0, warn: 0, detect: 0 };
  for (const t of tools) {
    if (t.decision_state in counts) counts[t.decision_state]++;
  }
  const items = [
    { state: 'block', label: 'Block', count: counts.block },
    { state: 'approval_required', label: 'Approval req.', count: counts.approval_required },
    { state: 'warn', label: 'Warn', count: counts.warn },
    { state: 'detect', label: 'Detect', count: counts.detect },
  ].filter((i) => i.count > 0);

  if (!items.length) return null;

  return (
    <div className="summary-bar">
      {items.map((i) => (
        <span key={i.state} className={`summary-chip summary-${i.state}`}>
          {i.label} <strong>{i.count}</strong>
        </span>
      ))}
    </div>
  );
}

function Dashboard({ summary }) {
  const { endpoint, tools, lastObserved, eventCount } = summary;

  return (
    <div className="dashboard">
      <EndpointHeader endpoint={endpoint} lastObserved={lastObserved} eventCount={eventCount} />
      <SummaryBar tools={tools} />
      <section className="tools-section">
        <h2>Detected AI tools <span className="tools-count">({tools.length})</span></h2>
        {tools.length === 0 ? (
          <p className="empty">No tools detected in this scan.</p>
        ) : (
          <table className="tools-table">
            <thead>
              <tr>
                <th>Tool</th>
                <th>Class</th>
                <th>Confidence</th>
                <th>Policy</th>
                <th>Severity</th>
                <th>Action summary</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool, i) => (
                <ToolRow key={`${tool.name}-${tool.class}-${i}`} tool={tool} />
              ))}
            </tbody>
          </table>
        )}
        <p className="table-hint">Click a row to expand details.</p>
      </section>
    </div>
  );
}

export default function App() {
  const { events, loading, error, loadFromApi, loadFromFile, refresh, canRefresh } = useEvents();
  const summary = buildEndpointSummary(events);

  return (
    <div className="app">
      <div className="app-bar">
        <div className="app-bar-left">
          <h1>Agentic Governance</h1>
          <span className="app-subtitle">Endpoint AI telemetry</span>
        </div>
        <div className="actions">
          <button type="button" onClick={loadFromApi} disabled={loading}>
            {loading ? 'Loading…' : 'Load from server'}
          </button>
          <label className="file-label">
            <input
              type="file"
              accept=".ndjson,application/x-ndjson"
              onChange={(e) => e.target.files?.[0] && loadFromFile(e.target.files[0])}
              style={{ display: 'none' }}
            />
            Load file…
          </label>
          {canRefresh && (
            <button type="button" onClick={refresh} disabled={loading} className="btn-refresh">
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
          )}
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}

      {events.length > 0 ? (
        <Dashboard summary={summary} />
      ) : !loading && !error ? (
        <div className="empty-state">
          <p>Load NDJSON from the server or choose a local file to inspect scan results.</p>
          <p>
            Run the collector:{' '}
            <code>cd collector &amp;&amp; python main.py --dry-run --verbose</code>
            {' '}(stdout) or without <code>--dry-run</code> to write <code>scan-results.ndjson</code>.
          </p>
          <p>Then start the server: <code>cd dashboard &amp;&amp; npm run dev</code></p>
        </div>
      ) : null}
    </div>
  );
}
