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
      if (!res.ok) throw new Error(res.status === 404 ? 'No NDJSON file served. Use "Load file" or start the server with NDJSON_PATH.' : `${res.status}`);
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
          if (!res.ok) throw new Error(res.status === 404 ? 'No NDJSON file served.' : `${res.status}`);
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
        try {
          setEvents(parseNdjson(reader.result));
        } catch (e) {
          setError(e.message);
          setEvents([]);
        }
        setLoading(false);
      };
      reader.onerror = () => {
        setError('Failed to read file');
        setLoading(false);
      };
      reader.readAsText(lastFile);
    }
  }, [source, lastFile]);

  const canRefresh = events.length > 0 && (source === 'api' || lastFile);

  return { events, loading, error, loadFromApi, loadFromFile, refresh, canRefresh };
}

function EndpointHeader({ endpoint, lastObserved }) {
  if (!endpoint) return null;
  return (
    <header className="endpoint-header">
      <div className="endpoint-id">{endpoint.id}</div>
      <div className="endpoint-meta">
        <span>{endpoint.os}</span>
        <span className="sep">·</span>
        <span>{endpoint.posture}</span>
        {lastObserved && (
          <>
            <span className="sep">·</span>
            <span className="last-scan">Last scan: {new Date(lastObserved).toLocaleString()}</span>
          </>
        )}
      </div>
    </header>
  );
}

function ToolRow({ tool }) {
  const decisionClass = {
    detect: 'decision-detect',
    warn: 'decision-warn',
    approval_required: 'decision-approval',
    block: 'decision-block',
  }[tool.decision_state] || '';

  return (
    <tr>
      <td className="tool-name">{tool.name}</td>
      <td className="tool-class">Class {tool.class}</td>
      <td>
        <span className={`confidence confidence-${tool.confidenceBand.toLowerCase()}`}>
          {tool.confidenceBand}
        </span>
        {tool.attribution_confidence != null && (
          <span className="confidence-value"> ({Math.round(tool.attribution_confidence * 100)}%)</span>
        )}
      </td>
      <td>
        <span className={`decision ${decisionClass}`}>{tool.policyLabel}</span>
      </td>
      <td className="reason">
        {tool.reason_codes?.length ? tool.reason_codes.join(', ') : (tool.summary || '—')}
      </td>
    </tr>
  );
}

function Dashboard({ summary }) {
  const { endpoint, tools, lastObserved } = summary;

  return (
    <div className="dashboard">
      <EndpointHeader endpoint={endpoint} lastObserved={lastObserved} />
      <section className="tools-section">
        <h2>Detected AI tools</h2>
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
                <th>Reason / summary</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool, i) => (
                <ToolRow key={`${tool.name}-${tool.class}-${i}`} tool={tool} />
              ))}
            </tbody>
          </table>
        )}
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
        <h1>Agentic Governance — Endpoint view</h1>
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

      {error && (
        <div className="banner error">
          {error}
        </div>
      )}

      {events.length > 0 ? (
        <Dashboard summary={summary} />
      ) : !loading && !error ? (
        <div className="empty-state">
          <p>Load NDJSON from the server (default: <code>collector/scan-results.ndjson</code>) or choose a file.</p>
          <p>Run the collector: <code>cd collector && python main.py --dry-run</code> prints to stdout; without <code>--dry-run</code> it writes to <code>scan-results.ndjson</code>.</p>
        </div>
      ) : null}
    </div>
  );
}
