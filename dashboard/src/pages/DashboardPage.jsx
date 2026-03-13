import { useState, useMemo, useCallback, useEffect } from 'react';
import useEndpoints from '../hooks/useEndpoints';
import usePolling from '../hooks/usePolling';
import { fetchEvents, getApiConfig } from '../lib/api';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';
import SummaryCards from '../components/dashboard/SummaryCards';
import FilterBar from '../components/dashboard/FilterBar';
import EndpointContextBar from '../components/dashboard/EndpointContextBar';
import ToolTabs from '../components/dashboard/ToolTabs';
import ToolsTable from '../components/dashboard/ToolsTable';
import Pagination from '../components/dashboard/Pagination';
import PostureSummaryWidget from '../components/dashboard/PostureSummaryWidget';
import DataFlowWidget from '../components/dashboard/DataFlowWidget';
import ResponseTimelineWidget from '../components/dashboard/ResponseTimelineWidget';
import SystemStatusBanner from '../components/dashboard/SystemStatusBanner';

export default function DashboardPage({ onNavigate, searchQuery = '', refreshRef, onAlertCountChange }) {
  const {
    tools, counts, endpointCount, endpoints, endpointStatuses,
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

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
  };

  const handlePageSizeChange = (size) => {
    setPageSize(size);
    setPage(1);
  };

  const handleTimeRangeChange = useCallback((observedAfter) => {
    updateFilters({ observedAfter });
    setPage(1);
  }, [updateFilters]);

  const handleEndpointChange = useCallback((endpointId) => {
    updateFilters({ endpointId });
    setPage(1);
  }, [updateFilters]);

  return (
    <div className="space-y-5 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <h1 className="text-xl sm:text-2xl font-bold text-detec-slate-100">AI Asset Inventory</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        {loading && <ApertureSpinner size="sm" label="Scanning" />}
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          <p>{error}</p>
          <p className="text-detec-slate-400 mt-1 text-xs">Check the connection and try again.</p>
        </div>
      )}

      <FilterBar
        endpoints={endpoints}
        selectedEndpoint={filters.endpointId}
        onEndpointChange={handleEndpointChange}
        timeRange={filters.observedAfter}
        onTimeRangeChange={handleTimeRangeChange}
      />

      <SystemStatusBanner counts={counts} endpoints={endpoints} />

      <SummaryCards counts={counts} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <PostureSummaryWidget onPostureReset={refresh} />
        <DataFlowWidget />
        <ResponseTimelineWidget onNavigate={onNavigate} />
      </div>

      <EndpointContextBar
        endpointCount={endpointCount}
        endpoints={endpoints}
        endpointStatuses={endpointStatuses}
        onPostureChange={refresh}
        lastEventAt={lastEventAt}
      />

      <ToolTabs
        activeTab={activeTab}
        onTabChange={handleTabChange}
        counts={counts}
        totalTools={tools.length}
      />

      {!loading && !error && tools.length === 0 && (
        <div className="rounded-lg border border-detec-slate-700/50 bg-detec-slate-800/30 px-6 py-10 text-center">
          <p className="text-detec-slate-300 font-medium">No AI tools detected yet</p>
          <p className="text-sm text-detec-slate-500 mt-1 max-w-md mx-auto">
            Run the Detec agent on your endpoints to send events. Detected tools and their policy status will appear here. This table is your AI tool and asset inventory.
          </p>
          <button
            type="button"
            onClick={() => onNavigate('events')}
            className="mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-detec-primary-500/20 text-detec-primary-400 hover:bg-detec-primary-500/30"
          >
            View Events
          </button>
        </div>
      )}

      {tools.length > 0 && <ToolsTable tools={paginatedTools} />}

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
