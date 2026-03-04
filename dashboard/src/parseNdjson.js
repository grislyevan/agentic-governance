/**
 * Parse NDJSON string into array of event objects.
 * Maps canonical event schema to a single-endpoint summary.
 */

/**
 * @param {string} raw
 * @returns {Array<Record<string, unknown>>}
 */
export function parseNdjson(raw) {
  const lines = raw.trim().split('\n').filter(Boolean);
  const events = [];
  for (const line of lines) {
    try {
      events.push(JSON.parse(line));
    } catch (_) {
      // skip invalid lines
    }
  }
  return events;
}

/** Confidence band from 0–1 score — thresholds from Playbook Section 6.2 */
export function confidenceBand(score) {
  if (score == null || typeof score !== 'number') return '—';
  if (score >= 0.75) return 'High';
  if (score >= 0.45) return 'Medium';
  return 'Low';
}

/** Policy decision label */
export function policyLabel(decision) {
  const labels = {
    detect: 'Detect',
    warn: 'Warn',
    approval_required: 'Approval Required',
    block: 'Block',
  };
  return labels[decision] ?? decision ?? '—';
}

/** Severity label from S0–S4 */
export function severityLabel(level) {
  const labels = { S0: 'S0', S1: 'S1', S2: 'S2', S3: 'S3', S4: 'S4' };
  return labels[level] ?? level ?? '—';
}

/**
 * Build single-endpoint summary from events.
 * One row per detected tool; merges detection.observed + policy.evaluated +
 * enforcement.applied events keyed by tool name.
 */
export function buildEndpointSummary(events) {
  const KNOWN_TYPES = new Set([
    'detection.observed',
    'policy.evaluated',
    'enforcement.applied',
  ]);
  const withTool = events.filter((e) => e.tool && KNOWN_TYPES.has(e.event_type));
  if (withTool.length === 0) {
    return { endpoint: null, tools: [], lastObserved: null, eventCount: events.length };
  }

  // Sort by observed_at desc so we keep the latest per tool per event type
  const sorted = [...withTool].sort(
    (a, b) => new Date(b.observed_at || 0) - new Date(a.observed_at || 0)
  );

  // Accumulate all event types per tool key; policy.evaluated wins for policy fields
  const detection = new Map();
  const policy = new Map();
  const enforcement = new Map();

  for (const ev of sorted) {
    const name = ev.tool?.name ?? 'Unknown';
    const key = `${name}|${ev.tool?.class ?? ''}`;
    if (ev.event_type === 'detection.observed' && !detection.has(key)) detection.set(key, ev);
    if (ev.event_type === 'policy.evaluated' && !policy.has(key)) policy.set(key, ev);
    if (ev.event_type === 'enforcement.applied' && !enforcement.has(key)) enforcement.set(key, ev);
  }

  // Merge: union of all tool keys
  const allKeys = new Set([
    ...detection.keys(),
    ...policy.keys(),
    ...enforcement.keys(),
  ]);

  const tools = Array.from(allKeys).map((key) => {
    const det = detection.get(key);
    const pol = policy.get(key);
    const enf = enforcement.get(key);
    const base = pol ?? det ?? enf;

    const confidence = base?.tool?.attribution_confidence ?? null;
    const decisionState = pol?.policy?.decision_state ?? det?.policy?.decision_state ?? null;
    const severityLevel = base?.severity?.level ?? null;
    const actionSummary = (det ?? pol)?.action?.summary ?? '';
    const reasonCodes = pol?.policy?.reason_codes ?? det?.policy?.reason_codes ?? [];
    const enforcementApplied = enf?.policy?.decision_state ?? null;

    return {
      name: base?.tool?.name ?? 'Unknown',
      class: base?.tool?.class ?? '—',
      version: base?.tool?.version ?? null,
      attribution_confidence: confidence,
      confidenceBand: confidenceBand(confidence),
      decision_state: decisionState,
      policyLabel: policyLabel(decisionState),
      severity_level: severityLevel,
      enforcement_applied: enforcementApplied,
      reason_codes: reasonCodes,
      summary: actionSummary,
      observed_at: base?.observed_at,
    };
  });

  // Sort: highest severity first, then by name
  const severityOrder = { S4: 4, S3: 3, S2: 2, S1: 1, S0: 0, null: -1 };
  tools.sort((a, b) => {
    const sa = severityOrder[a.severity_level] ?? -1;
    const sb = severityOrder[b.severity_level] ?? -1;
    if (sb !== sa) return sb - sa;
    return (a.name ?? '').localeCompare(b.name ?? '');
  });

  const first = events.find((e) => e.endpoint);
  const endpoint = first?.endpoint
    ? {
        id: first.endpoint.id,
        os: first.endpoint.os,
        posture: first.endpoint.posture,
      }
    : null;

  const dates = events.map((e) => e.observed_at).filter(Boolean);
  const lastObserved = dates.length ? dates.sort().reverse()[0] : null;

  return { endpoint, tools, lastObserved, eventCount: events.length };
}
