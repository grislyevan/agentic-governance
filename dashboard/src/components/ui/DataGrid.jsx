import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

/**
 * DataGrid -- Unified dense data grid for the Detec SOC dashboard.
 *
 * Replaces per-page table implementations with a single, keyboard-navigable,
 * sortable, expandable CSS-Grid table styled to the Detec design system.
 *
 * @example
 * <DataGrid
 *   columns={[
 *     { key: 'observed_at', label: 'Time', width: '140px', mono: true },
 *     { key: 'tool_name',   label: 'Tool', width: '1fr' },
 *   ]}
 *   rows={events}
 *   rowKey="event_id"
 *   sortKey="observed_at"
 *   sortDir="desc"
 *   onSort={(key, dir) => {}}
 *   expandable
 *   renderExpanded={(row) => <Detail event={row} />}
 * />
 */

// Deterministic skeleton widths so re-renders don't flicker
const SKELETON_WIDTHS = [62, 45, 78, 53, 70];

// ---------------------------------------------------------------------------
// Sort chevron icon (inline SVG, no external deps)
// ---------------------------------------------------------------------------
const SORT_ICONS = {
  asc: (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" aria-hidden="true">
      <path d="M5 2L8.5 7H1.5L5 2Z" />
    </svg>
  ),
  desc: (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" aria-hidden="true">
      <path d="M5 8L1.5 3H8.5L5 8Z" />
    </svg>
  ),
  neutral: (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" aria-hidden="true" className="opacity-30">
      <path d="M5 1L7.5 4.5H2.5L5 1Z" />
      <path d="M5 9L2.5 5.5H7.5L5 9Z" />
    </svg>
  ),
};

// ---------------------------------------------------------------------------
// Build the CSS grid-template-columns string from column definitions
// ---------------------------------------------------------------------------
function buildGridTemplate(columns) {
  return columns.map((c) => c.width || '1fr').join(' ');
}

// ---------------------------------------------------------------------------
// Sort cycle: none -> asc -> desc -> none
// ---------------------------------------------------------------------------
function nextSortState(currentKey, currentDir, clickedKey) {
  if (currentKey !== clickedKey) return { key: clickedKey, dir: 'asc' };
  if (currentDir === 'asc') return { key: clickedKey, dir: 'desc' };
  if (currentDir === 'desc') return { key: null, dir: null };
  return { key: clickedKey, dir: 'asc' };
}

// ---------------------------------------------------------------------------
// Alignment class helper
// ---------------------------------------------------------------------------
function alignClass(align) {
  if (align === 'right') return 'text-right justify-end';
  if (align === 'center') return 'text-center justify-center';
  return 'text-left justify-start';
}

// ---------------------------------------------------------------------------
// DataGrid Component
// ---------------------------------------------------------------------------
export default function DataGrid({
  columns = [],
  rows = [],
  rowKey = 'id',
  onRowClick,
  expandable = false,
  renderExpanded,
  emptyMessage = 'No data found',
  loading = false,
  sortKey: controlledSortKey,
  sortDir: controlledSortDir,
  onSort,
  className = '',
}) {
  // ---- Sort state (internal fallback when uncontrolled) ----
  const [internalSortKey, setInternalSortKey] = useState(controlledSortKey ?? null);
  const [internalSortDir, setInternalSortDir] = useState(controlledSortDir ?? null);

  const isControlled = onSort !== undefined;
  const activeSortKey = isControlled ? controlledSortKey : internalSortKey;
  const activeSortDir = isControlled ? controlledSortDir : internalSortDir;

  const handleSort = useCallback(
    (colKey) => {
      const { key, dir } = nextSortState(activeSortKey, activeSortDir, colKey);
      if (isControlled) {
        onSort(key, dir);
      } else {
        setInternalSortKey(key);
        setInternalSortDir(dir);
      }
    },
    [activeSortKey, activeSortDir, isControlled, onSort],
  );

  // ---- Expand state (single row at a time) ----
  const [expandedRowId, setExpandedRowId] = useState(null);

  const toggleExpanded = useCallback(
    (id) => {
      setExpandedRowId((prev) => (prev === id ? null : id));
    },
    [],
  );

  // ---- Keyboard navigation ----
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const gridRef = useRef(null);

  // Keep focused index within bounds when rows change
  useEffect(() => {
    if (focusedIndex >= rows.length) {
      setFocusedIndex(rows.length > 0 ? rows.length - 1 : -1);
    }
  }, [rows.length, focusedIndex]);

  const handleKeyDown = useCallback(
    (e) => {
      if (loading || rows.length === 0) return;

      const key = e.key;
      let handled = true;

      switch (key) {
        case 'ArrowDown':
        case 'j':
          setFocusedIndex((prev) => Math.min(prev + 1, rows.length - 1));
          break;
        case 'ArrowUp':
        case 'k':
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case 'Enter': {
          if (focusedIndex < 0 || focusedIndex >= rows.length) break;
          const row = rows[focusedIndex];
          const id = row[rowKey];
          if (expandable && renderExpanded) {
            toggleExpanded(id);
          } else if (onRowClick) {
            onRowClick(row);
          }
          break;
        }
        case 'Escape':
          setExpandedRowId(null);
          break;
        default:
          handled = false;
      }

      if (handled) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    [loading, rows, rowKey, focusedIndex, expandable, renderExpanded, onRowClick, toggleExpanded],
  );

  // Scroll focused row into view
  useEffect(() => {
    if (focusedIndex < 0 || !gridRef.current) return;
    const row = gridRef.current.querySelector(`[data-row-index="${focusedIndex}"]`);
    if (row) {
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [focusedIndex]);

  // ---- Internal sort for uncontrolled mode ----
  const sortedRows = useMemo(() => {
    if (isControlled || !activeSortKey || !activeSortDir) return rows;

    return [...rows].sort((a, b) => {
      const aVal = a[activeSortKey];
      const bVal = b[activeSortKey];

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      let cmp;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        cmp = aVal - bVal;
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }
      return activeSortDir === 'desc' ? -cmp : cmp;
    });
  }, [rows, activeSortKey, activeSortDir, isControlled]);

  // ---- Grid template ----
  const gridTemplate = useMemo(() => buildGridTemplate(columns), [columns]);

  // ---- Render ----
  return (
    <div
      className={`bg-detec-surface border border-detec-edge rounded-detec-md overflow-hidden ${className}`}
    >
      <div className="overflow-x-auto">
        <div
          ref={gridRef}
          role="grid"
          tabIndex={0}
          aria-rowcount={sortedRows.length}
          aria-colcount={columns.length}
          onKeyDown={handleKeyDown}
          className="min-w-full focus:outline-none"
        >
          {/* ---- Header ---- */}
          <div
            role="row"
            aria-rowindex={1}
            className="sticky top-0 z-10 bg-detec-ground border-b border-detec-edge"
            style={{
              display: 'grid',
              gridTemplateColumns: gridTemplate,
              height: '32px',
            }}
          >
            {columns.map((col) => {
              const isSortable = col.sortable !== false;
              const isActive = activeSortKey === col.key;
              const icon = isActive
                ? SORT_ICONS[activeSortDir] || SORT_ICONS.neutral
                : SORT_ICONS.neutral;

              return (
                <div
                  key={col.key}
                  role="columnheader"
                  aria-sort={
                    isActive && activeSortDir === 'asc'
                      ? 'ascending'
                      : isActive && activeSortDir === 'desc'
                        ? 'descending'
                        : 'none'
                  }
                  className={`
                    flex items-center gap-1 px-3 group
                    text-data-xs font-medium text-detec-ink-tertiary uppercase tracking-wider
                    select-none
                    ${alignClass(col.align)}
                    ${isSortable ? 'cursor-pointer hover:text-detec-ink-secondary transition-colors duration-75' : ''}
                  `}
                  onClick={isSortable ? () => handleSort(col.key) : undefined}
                >
                  <span className="truncate">{col.label}</span>
                  {isSortable && (
                    <span
                      className={`flex-shrink-0 transition-opacity duration-75 ${
                        isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'
                      }`}
                    >
                      {icon}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* ---- Loading skeleton ---- */}
          {loading && (
            <div role="status" aria-label="Loading">
              {SKELETON_WIDTHS.map((baseWidth, i) => (
                <div
                  key={`skel-${i}`}
                  role="row"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: gridTemplate,
                    height: '36px',
                  }}
                  className="border-b border-detec-edge"
                >
                  {columns.map((col, ci) => (
                    <div
                      key={col.key}
                      className={`flex items-center px-3 ${alignClass(col.align)}`}
                    >
                      <div
                        className="bg-detec-raised animate-pulse rounded-detec"
                        style={{
                          height: '12px',
                          width: `${((baseWidth + ci * 17) % 40) + 40}%`,
                          minWidth: '24px',
                        }}
                      />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* ---- Empty state ---- */}
          {!loading && sortedRows.length === 0 && (
            <div
              role="row"
              className="flex items-center justify-center border-b border-detec-edge"
              style={{ height: '120px' }}
            >
              <div role="gridcell" className="text-sm text-detec-ink-secondary">
                {emptyMessage}
              </div>
            </div>
          )}

          {/* ---- Data rows ---- */}
          {!loading &&
            sortedRows.map((row, index) => {
              const id = row[rowKey];
              const isExpanded = expandedRowId === id;
              const isFocused = focusedIndex === index;
              const isClickable = expandable || !!onRowClick;

              return (
                <div key={id} data-row-index={index}>
                  {/* Row */}
                  <div
                    role="row"
                    aria-rowindex={index + 2}
                    aria-selected={isExpanded}
                    data-row-id={id}
                    className={`
                      border-b border-detec-edge transition-colors duration-75
                      ${isExpanded ? 'bg-detec-raised' : 'hover:bg-detec-raised'}
                      ${isClickable ? 'cursor-pointer' : ''}
                      ${isFocused ? 'ring-1 ring-inset ring-detec-brand/30' : ''}
                    `}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: gridTemplate,
                      height: '36px',
                    }}
                    onClick={() => {
                      setFocusedIndex(index);
                      if (expandable && renderExpanded) {
                        toggleExpanded(id);
                      } else if (onRowClick) {
                        onRowClick(row);
                      }
                    }}
                  >
                    {columns.map((col) => {
                      const value = row[col.key];
                      const rendered = col.render ? col.render(value, row) : value;

                      return (
                        <div
                          key={col.key}
                          role="gridcell"
                          className={`
                            flex items-center px-3 truncate
                            text-data text-detec-ink-primary
                            ${alignClass(col.align)}
                            ${col.mono ? 'font-data' : ''}
                          `}
                        >
                          <span className="truncate">
                            {rendered != null ? rendered : '\u2014'}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Expanded panel */}
                  {expandable && isExpanded && renderExpanded && (
                    <div
                      role="row"
                      aria-rowindex={index + 2}
                      className="bg-detec-void border-t border-detec-edge-emphasis"
                    >
                      <div role="gridcell" className="p-4">
                        {renderExpanded(row)}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
