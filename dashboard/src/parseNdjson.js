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

/** Confidence band from 0–1 score */
export function confidenceBand(score) {
  if (score == null || typeof score !== 'number') return '—';
  if (score >= 0.67) return 'High';
  if (score >= 0.34) return 'Medium';
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

/**
 * Build single-endpoint summary from events.
 * One row per detected tool; prefer policy.evaluated for decision.
 */
export function buildEndpointSummary(events) {
  const withTool = events.filter((e) => e.tool && (e.event_type === 'detection.observed' || e.event_type === 'policy.evaluated'));
  if (withTool.length === 0) {
    return { endpoint: null, tools: [], lastObserved: null };
  }

  // Sort by observed_at desc so we keep latest per tool
  const sorted = [...withTool].sort(
    (a, b) => new Date(b.observed_at || 0) - new Date(a.observed_at || 0)
  );

  const byToolKey = new Map();
  for (const ev of sorted) {
    const name = ev.tool?.name ?? 'Unknown';
    const key = `${name}|${ev.tool?.class ?? ''}`;
    if (byToolKey.has(key)) continue;
    byToolKey.set(key, ev);
  }

  const tools = Array.from(byToolKey.values()).map((ev) => ({
    name: ev.tool?.name ?? 'Unknown',
    class: ev.tool?.class ?? '—',
    attribution_confidence: ev.tool?.attribution_confidence,
    confidenceBand: confidenceBand(ev.tool?.attribution_confidence),
    decision_state: ev.policy?.decision_state ?? null,
    policyLabel: policyLabel(ev.policy?.decision_state),
    reason_codes: ev.policy?.reason_codes ?? [],
    summary: ev.action?.summary ?? '',
    observed_at: ev.observed_at,
  }));

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

  return { endpoint, tools, lastObserved };
}
