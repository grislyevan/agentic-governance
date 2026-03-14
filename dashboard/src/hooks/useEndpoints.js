import { useState, useCallback, useEffect } from 'react';
import { fetchEndpoints, fetchEndpointStatus, fetchEndpointProfiles, fetchAllEvents, getApiConfig } from '../lib/api';
import { getStoredTokens } from '../lib/auth';
import { confidenceBand, policyLabel } from '../parseNdjson';

function aggregateEvents(events) {
  const KNOWN_TYPES = new Set([
    'detection.observed',
    'policy.evaluated',
    'enforcement.applied',
    'enforcement.simulated',
    'tool.detected',
    'detection',
  ]);
  const toolMap = new Map();

  for (const ev of events) {
    const tool = ev.tool || (ev.tool_name ? { name: ev.tool_name, class: ev.tool_class, version: ev.tool_version } : null);
    if (!tool?.name || !KNOWN_TYPES.has(ev.event_type)) continue;
    const name = tool.name ?? ev.tool_name ?? 'Unknown';
    const key = name;

    if (!toolMap.has(key)) {
      toolMap.set(key, {
        name,
        class: tool.class ?? ev.tool_class ?? '-',
        version: tool.version ?? ev.tool_version ?? null,
        attribution_confidence: tool.attribution_confidence ?? ev.attribution_confidence ?? null,
        confidenceBand: confidenceBand(tool.attribution_confidence ?? ev.attribution_confidence),
        decision_state: ev.decision_state ?? null,
        policyLabel: ev.decision_state ? policyLabel(ev.decision_state) : '-',
        severity_level: ev.severity_level ?? ev.severity?.level ?? null,
        rule_id: ev.rule_id ?? null,
        reason_codes: ev.policy?.reason_codes ?? [],
        summary: '',
        observed_at: ev.observed_at,
        enforcement_applied: null,
        endpoint_id: ev.endpoint?.id ?? ev.endpoint_id ?? null,
      });
    }

    const entry = toolMap.get(key);

    if (ev.event_type === 'policy.evaluated' || ev.event_type === 'enforcement.applied' || ev.event_type === 'enforcement.simulated') {
      const ds = ev.policy?.decision_state;
      if (ds) {
        entry.decision_state = ds;
        entry.policyLabel = policyLabel(ds);
      }
      if (ev.policy?.rule_id) entry.rule_id = ev.policy.rule_id;
      if (ev.policy?.reason_codes?.length) entry.reason_codes = ev.policy.reason_codes;
    }

    if (ev.severity?.level) entry.severity_level = ev.severity.level;
    if (ev.decision_state) {
      entry.decision_state = ev.decision_state;
      entry.policyLabel = policyLabel(ev.decision_state);
    }
    if (ev.rule_id) entry.rule_id = ev.rule_id;
    if (ev.action?.summary) entry.summary = ev.action.summary;
    if (ev.event_type === 'enforcement.applied') entry.enforcement_applied = ev.policy?.decision_state;

    const evTime = new Date(ev.observed_at || 0).getTime();
    const existingTime = new Date(entry.observed_at || 0).getTime();
    if (evTime > existingTime) {
      entry.observed_at = ev.observed_at;
      if (ev.tool?.attribution_confidence != null) {
        entry.attribution_confidence = ev.tool.attribution_confidence;
        entry.confidenceBand = confidenceBand(ev.tool.attribution_confidence);
      }
    }
  }

  const tools = Array.from(toolMap.values());

  const severityOrder = { S4: 4, S3: 3, S2: 2, S1: 1, S0: 0 };
  tools.sort((a, b) => {
    const sa = severityOrder[a.severity_level] ?? -1;
    const sb = severityOrder[b.severity_level] ?? -1;
    if (sb !== sa) return sb - sa;
    return (a.name ?? '').localeCompare(b.name ?? '');
  });

  const counts = { block: 0, approval_required: 0, warn: 0, detect: 0 };
  for (const t of tools) {
    if (t.decision_state in counts) counts[t.decision_state]++;
  }

  const endpointIds = new Set(
    events
      .map((e) => e.endpoint?.id ?? e.endpoint_id)
      .filter(Boolean)
  );

  return { tools, counts, endpointCount: endpointIds.size, totalEvents: events.length };
}

export default function useEndpoints() {
  const [data, setData] = useState({
    tools: [],
    counts: { block: 0, approval_required: 0, warn: 0, detect: 0 },
    endpointCount: 0,
    totalEvents: 0,
    endpoints: [],
    endpointStatuses: [],
    profiles: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ observedAfter: null, endpointId: null });

  const load = useCallback(async (filterOverrides) => {
    const { accessToken } = getStoredTokens();
    const config = getApiConfig();
    if (!accessToken && !config.apiKey) {
      setError('No authentication credentials available.');
      return;
    }

    setLoading(true);
    setError(null);

    const activeFilters = filterOverrides || filters;

    try {
      const [events, epData, statuses, profilesData] = await Promise.all([
        fetchAllEvents(config, {
          observedAfter: activeFilters.observedAfter || undefined,
          endpointId: activeFilters.endpointId || undefined,
        }),
        fetchEndpoints(config).catch(() => ({ items: [], total: 0 })),
        fetchEndpointStatus(config).catch(() => []),
        fetchEndpointProfiles(config, { pageSize: 200 }).catch(() => ({ items: [] })),
      ]);

      const aggregated = aggregateEvents(events);

      setData({
        ...aggregated,
        endpoints: epData.items || [],
        endpointStatuses: Array.isArray(statuses) ? statuses : [],
        endpointCount: aggregated.endpointCount || (epData.items || []).length,
        profiles: profilesData?.items || [],
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const updateFilters = useCallback((newFilters) => {
    const merged = { ...filters, ...newFilters };
    setFilters(merged);
    load(merged);
  }, [filters, load]);

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...data, loading, error, refresh: () => load(), filters, updateFilters };
}
