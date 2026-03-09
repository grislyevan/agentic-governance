import { useState, useRef, useEffect } from 'react';

const TIME_RANGES = [
  { label: 'Last 1 Hour', value: 1 },
  { label: 'Last 6 Hours', value: 6 },
  { label: 'Last 24 Hours', value: 24 },
  { label: 'Last 7 Days', value: 168 },
  { label: 'Last 30 Days', value: 720 },
  { label: 'All Time', value: null },
];

function hoursToIso(hours) {
  if (!hours) return null;
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function labelForTimeRange(observedAfter) {
  if (!observedAfter) return 'All Time';
  const diff = (Date.now() - new Date(observedAfter).getTime()) / (60 * 60 * 1000);
  const match = TIME_RANGES.find(r => r.value && Math.abs(r.value - diff) < r.value * 0.1);
  return match?.label || 'Custom';
}

export default function FilterBar({ endpoints = [], selectedEndpoint, onEndpointChange, timeRange, onTimeRangeChange }) {
  const [showEpDropdown, setShowEpDropdown] = useState(false);
  const [showTimeDropdown, setShowTimeDropdown] = useState(false);
  const epRef = useRef(null);
  const timeRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (epRef.current && !epRef.current.contains(e.target)) setShowEpDropdown(false);
      if (timeRef.current && !timeRef.current.contains(e.target)) setShowTimeDropdown(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const selectedEpLabel = selectedEndpoint
    ? (endpoints.find(ep => ep.id === selectedEndpoint)?.hostname || 'Selected')
    : 'All Endpoints';

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        {/* Endpoint selector */}
        <div className="relative" ref={epRef}>
          <button
            onClick={() => setShowEpDropdown(!showEpDropdown)}
            aria-expanded={showEpDropdown}
            aria-haspopup="listbox"
            aria-label="Select endpoint"
            className="flex items-center gap-2 px-3 py-1.5 bg-detec-slate-800 border border-detec-slate-700 rounded-lg text-sm text-detec-slate-300 hover:border-detec-slate-600 transition-colors"
          >
            <span className="text-detec-slate-500 text-xs">View:</span>
            {selectedEpLabel}
            <ChevronDown />
          </button>
          {showEpDropdown && (
            <div className="absolute top-full mt-1 left-0 w-56 bg-detec-slate-800 border border-detec-slate-700 rounded-lg shadow-lg py-1 z-50 max-h-60 overflow-y-auto">
              <button
                onClick={() => { onEndpointChange?.(null); setShowEpDropdown(false); }}
                className={`w-full text-left px-3 py-2 text-sm transition-colors ${!selectedEndpoint ? 'text-detec-primary-400 bg-detec-primary-500/10' : 'text-detec-slate-300 hover:bg-detec-slate-700/50'}`}
              >
                All Endpoints
              </button>
              {endpoints.map(ep => (
                <button
                  key={ep.id}
                  onClick={() => { onEndpointChange?.(ep.id); setShowEpDropdown(false); }}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors ${selectedEndpoint === ep.id ? 'text-detec-primary-400 bg-detec-primary-500/10' : 'text-detec-slate-300 hover:bg-detec-slate-700/50'}`}
                >
                  <div>{ep.hostname}</div>
                  <div className="text-xs text-detec-slate-500">{ep.os_info || 'Unknown OS'}</div>
                </button>
              ))}
              {endpoints.length === 0 && (
                <div className="px-3 py-2 text-xs text-detec-slate-500">No endpoints registered</div>
              )}
            </div>
          )}
        </div>

        {/* Time range */}
        <div className="relative" ref={timeRef}>
          <button
            onClick={() => setShowTimeDropdown(!showTimeDropdown)}
            aria-expanded={showTimeDropdown}
            aria-haspopup="listbox"
            aria-label="Select time range"
            className="flex items-center gap-2 px-3 py-1.5 bg-detec-slate-800 border border-detec-slate-700 rounded-lg text-sm text-detec-slate-300 hover:border-detec-slate-600 transition-colors"
          >
            <CalendarIcon />
            {labelForTimeRange(timeRange)}
            <ChevronDown />
          </button>
          {showTimeDropdown && (
            <div className="absolute top-full mt-1 left-0 w-44 bg-detec-slate-800 border border-detec-slate-700 rounded-lg shadow-lg py-1 z-50">
              {TIME_RANGES.map(range => {
                const iso = hoursToIso(range.value);
                const isActive = (timeRange || null) === iso || (!timeRange && !range.value);
                return (
                  <button
                    key={range.label}
                    onClick={() => { onTimeRangeChange?.(iso); setShowTimeDropdown(false); }}
                    className={`w-full text-left px-3 py-2 text-sm transition-colors ${isActive ? 'text-detec-primary-400 bg-detec-primary-500/10' : 'text-detec-slate-300 hover:bg-detec-slate-700/50'}`}
                  >
                    {range.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <button
        className="flex items-center gap-2 px-4 py-1.5 bg-detec-primary-500/15 border border-detec-primary-500/30 rounded-lg text-sm font-medium text-detec-primary-400 hover:bg-detec-primary-500/25 transition-colors opacity-50 cursor-not-allowed"
        title="Acknowledge functionality coming soon"
        disabled
      >
        <CheckAllIcon />
        ACKNOWLEDGE ALL
      </button>
    </div>
  );
}

function ChevronDown() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function CheckAllIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="9 11 12 14 22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}
