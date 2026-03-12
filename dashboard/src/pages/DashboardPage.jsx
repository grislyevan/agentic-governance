import { useState, useMemo, useCallback, useEffect } from 'react';
import useEndpoints from '../hooks/useEndpoints';
import usePolling from '../hooks/usePolling';
import ApertureSpinner from '../components/branding/ApertureSpinner';
import PollingStatus from '../components/PollingStatus';
import SummaryCards from '../components/dashboard/SummaryCards';
import FilterBar from '../components/dashboard/FilterBar';
import EndpointContextBar from '../components/dashboard/EndpointContextBar';
import ToolTabs from '../components/dashboard/ToolTabs';
import ToolsTable from '../components/dashboard/ToolsTable';
import Pagination from '../components/dashboard/Pagination';
import PostureSummaryWidget from '../components/dashboard/PostureSummaryWidget';

export default function DashboardPage({ onNavigate, searchQuery = '', refreshRef, onAlertCountChange }) {
  const {
    tools, counts, endpointCount, endpoints, endpointStatuses,
    loading, error, refresh, filters, updateFilters,
  } = useEndpoints();

  const [activeTab, setActiveTab] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { lastUpdated, paused, togglePause } = usePolling(refresh);

  useEffect(() => {
    if (refreshRef) refreshRef.current = refresh;
  }, [refresh, refreshRef]);

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
          <h1 className="text-xl sm:text-2xl font-bold text-detec-slate-100">Dashboard</h1>
          <PollingStatus lastUpdated={lastUpdated} paused={paused} onTogglePause={togglePause} />
        </div>
        {loading && <ApertureSpinner size="sm" label="Scanning" />}
      </div>

      {error && (
        <div className="rounded-lg border border-detec-enforce-block/30 bg-detec-enforce-block/10 px-4 py-3 text-sm text-detec-enforce-block">
          {error}
        </div>
      )}

      <FilterBar
        endpoints={endpoints}
        selectedEndpoint={filters.endpointId}
        onEndpointChange={handleEndpointChange}
        timeRange={filters.observedAfter}
        onTimeRangeChange={handleTimeRangeChange}
      />

      <SummaryCards counts={counts} />

      <PostureSummaryWidget onPostureReset={refresh} />

      <EndpointContextBar
        endpointCount={endpointCount}
        endpoints={endpoints}
        endpointStatuses={endpointStatuses}
        onPostureChange={refresh}
      />

      <ToolTabs
        activeTab={activeTab}
        onTabChange={handleTabChange}
        counts={counts}
        totalTools={tools.length}
        onNavigate={onNavigate}
      />

      <ToolsTable tools={paginatedTools} />

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
