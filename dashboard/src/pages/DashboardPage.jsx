import { useState, useMemo, useCallback, useEffect } from 'react';
import useEndpoints from '../hooks/useEndpoints';
import usePolling from '../hooks/usePolling';
import { fetchEvents, getApiConfig } from '../lib/api';
import { getUserRole } from '../lib/auth';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';
import ApiErrorBanner from '../components/ui/ApiErrorBanner';
import ThreatPostureGauge from '../components/dashboard/ThreatPostureGauge';
import DetectionTimelineWidget from '../components/dashboard/DetectionTimelineWidget';
import FilterBar from '../components/dashboard/FilterBar';
import ToolTabs from '../components/dashboard/ToolTabs';
import ToolsTable from '../components/dashboard/ToolsTable';
import Pagination from '../components/dashboard/Pagination';
import PostureSummaryWidget from '../components/dashboard/PostureSummaryWidget';
import DataFlowWidget from '../components/dashboard/DataFlowWidget';
import ResponseTimelineWidget from '../components/dashboard/ResponseTimelineWidget';
import CapabilityDriftWidget from '../components/dashboard/CapabilityDriftWidget';

/* ── Fleet Status Strip ── */
function FleetStrip({ endpointCount, endpoints }) {
  const active = endpoints.filter((e) => e.status === 'active').length;
  const stale = endpoints.filter((e) => e.status === 'stale').length;
  const tamper = endpoints.filter((e) => e.status === 'tamper_suspected').length;
  const nativeCount = endpoints.filter((e) =>
    e.telemetry_provider === 'esf' || e.telemetry_provider === 'etw' || e.telemetry_provider === 'ebpf'
  ).length;
  const nativePct = endpointCount > 0 ? Math.round((nativeCount / endpointCount) * 100) : 0;

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 py-2.5 bg-detec-surface border border-detec-edge rounded-detec-md text-xs">
      <span className="font-medium text-detec-ink-primary font-data">{endpointCount}</span>
      <span className="text-detec-ink-secondary">endpoints</span>
      <span className="text-detec-edge">|</span>
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-detec-healthy" />
        <span className="font-data text-detec-ink-primary">{active}</span>
        <span className="text-detec-ink-tertiary">active</span>
      </span>
      {stale > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-detec-stale" />
          <span className="font-data text-detec-ink-primary">{stale}</span>
          <span className="text-detec-ink-tertiary">stale</span>
        </span>
      )}
      {tamper > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-detec-critical" />
          <span className="font-data text-detec-ink-primary">{tamper}</span>
          <span className="text-detec-ink-tertiary">tamper</span>
        </span>
      )}
      <span className="text-detec-edge">|</span>
      <span className="text-detec-ink-secondary">
        Signal: Native <span className="font-data text-detec-ink-primary">{nativePct}%</span>
      </span>
    </div>
  );
}

export default function DashboardPage({ onNavigate, searchQuery = '', refreshRef, onAlertCountChange }) {
  const isAdminOrOwner = ['owner', 'admin'].includes(getUserRole());

  const {
    tools, counts, endpointCount, endpoints, profiles,
    loading, error, refresh, filters, updateFilters,
  } = useEndpoints();

  const [activeTab, setActiveTab] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [lastEventAt, setLastEventAt] = useState(null);
  const refreshWithLatestEvent = useCallback(async () => {
    await refresh();
    const config = getApiConfig();
    try {
      const data = await fetchEvents(config, { pageSize: 1 });
      setLastEventAt(data.items?.[0]?.observed_at ?? null);
    } catch {
      setLastEventAt(null);
    }
  }, [refresh]);

  const { lastUpdated, paused, togglePause } = usePolling(refreshWithLatestEvent);

  useEffect(() => {
    if (refreshRef) refreshRef.current = refreshWithLatestEvent;
  }, [refreshWithLatestEvent, refreshRef]);

  useEffect(() => {
    const config = getApiConfig();
    if (!config.apiKey && !config.accessToken) return;
    fetchEvents(config, { pageSize: 1 })
      .then((data) => setLastEventAt(data.items?.[0]?.observed_at ?? null))
      .catch(() => setLastEventAt(null));
  }, []);

  useEffect(() => {
    const alertCount = (counts.block || 0) + (counts.approval_required || 0);
    onAlertCountChange?.(alertCount);
  }, [counts, onAlertCountChange]);

  const filteredTools = useMemo(() => {
    let result = tools;
    if (activeTab !== 'all') {
      result = result.filter((t) => t.decision_state === activeTab);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((t) =>
        t.name?.toLowerCase().includes(q) ||
        t.rule_id?.toLowerCase().includes(q) ||
        t.summary?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [tools, activeTab, searchQuery]);

  const paginatedTools = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredTools.slice(start, start + pageSize);
  }, [filteredTools, page, pageSize]);

  const handleTabChange = (tab) => { setActiveTab(tab); setPage(1); };
  const handlePageSizeChange = (size) => { setPageSize(size); setPage(1); };

  const handleTimeRangeChange = useCallback((observedAfter) => {
    updateFilters({ observedAfter });
    setPage(1);
  }, [updateFilters]);

  const handleEndpointChange = useCallback((endpointId) => {
    updateFilters({ endpointId });
    setPage(1);
  }, [updateFilters]);

  return (
    <div className="space-y-4 min-w-0">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">Overview</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
          {loading && <ApertureSpinner size="sm" label="Scanning" />}
        </div>
        <FilterBar
          endpoints={endpoints}
          selectedEndpoint={filters.endpointId}
          onEndpointChange={handleEndpointChange}
          timeRange={filters.observedAfter}
          onTimeRangeChange={handleTimeRangeChange}
        />
      </div>

      <ApiErrorBanner error={error} />

      {/* ── Fleet Status Strip ── */}
      <FleetStrip endpointCount={endpointCount} endpoints={endpoints} />

      {/* ── Top Row: Threat Gauge + Posture + Approvals ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-2">
          <ThreatPostureGauge
            counts={counts}
            onSegmentClick={(key) => handleTabChange(key)}
          />
        </div>
        {isAdminOrOwner && (
          <div data-testid="posture-summary-widget">
            <PostureSummaryWidget onPostureReset={refresh} />
          </div>
        )}
        <ResponseTimelineWidget onNavigate={onNavigate} />
      </div>

      {/* ── Detection Timeline (full width) ── */}
      <DetectionTimelineWidget onNavigate={onNavigate} />

      {/* ── Bottom Row: Data Flow + Capability Drift ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DataFlowWidget />
        {isAdminOrOwner && <CapabilityDriftWidget onNavigate={onNavigate} />}
      </div>

      {/* ── Tools Table ── */}
      <ToolTabs
        activeTab={activeTab}
        onTabChange={handleTabChange}
        counts={counts}
        totalTools={tools.length}
      />

      {!loading && !error && tools.length === 0 && (
        <div className="rounded-detec-md border border-detec-edge bg-detec-surface px-6 py-10 text-center">
          <p className="text-detec-ink-primary font-medium">No AI tools detected yet</p>
          <p className="text-sm text-detec-ink-secondary mt-1 max-w-md mx-auto">
            Deploy the Detec agent to start monitoring AI tools on your endpoints.
          </p>
          <button
            type="button"
            onClick={() => onNavigate('detections')}
            className="mt-4 px-4 py-2 rounded-detec-md text-sm font-medium bg-detec-brand-muted text-detec-brand hover:bg-detec-brand/20"
          >
            View Events
          </button>
        </div>
      )}

      {tools.length > 0 && <ToolsTable tools={paginatedTools} onNavigate={onNavigate} />}

      {filteredTools.length > 0 && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={filteredTools.length}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
        />
      )}
    </div>
  );
}
