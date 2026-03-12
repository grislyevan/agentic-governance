export default function Pagination({ page, pageSize, total, onPageChange, onPageSizeChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const pages = buildPageNumbers(page, totalPages);

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm">
      {/* Left: total count */}
      <div className="text-detec-slate-500 order-2 sm:order-1">
        Tool Scanners <span className="text-detec-slate-400 font-medium">{total} total</span>
      </div>

      {/* Center: page numbers */}
      <div className="flex items-center gap-1">
        <NavButton
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeftIcon />
        </NavButton>
        <NavButton
          onClick={() => onPageChange(1)}
          disabled={page <= 1}
          aria-label="First page"
        >
          <ChevronLeftIcon />
          <ChevronLeftIcon className="-ml-1.5" />
        </NavButton>

        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`dots-${i}`} className="px-1 text-detec-slate-600">...</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`
                min-w-[32px] h-8 px-2 rounded-md text-sm font-medium transition-colors
                ${p === page
                  ? 'bg-detec-primary-500/20 text-detec-primary-400 border border-detec-primary-500/30'
                  : 'text-detec-slate-400 hover:text-detec-slate-200 hover:bg-detec-slate-800'
                }
              `}
            >
              {p}
            </button>
          )
        )}

        <NavButton
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          aria-label="Next page"
        >
          <ChevronRightIcon />
        </NavButton>
        <NavButton
          onClick={() => onPageChange(totalPages)}
          disabled={page >= totalPages}
          aria-label="Last page"
        >
          <ChevronRightIcon />
          <ChevronRightIcon className="-ml-1.5" />
        </NavButton>
      </div>

      {/* Right: page size */}
      <div className="flex items-center gap-2">
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          aria-label="Rows per page"
          className="bg-detec-slate-800 border border-detec-slate-700 rounded-md px-2 py-1 text-sm text-detec-slate-300 focus:outline-none focus:border-detec-primary-500/50"
        >
          {[10, 20, 50].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-detec-slate-500">Rows</span>
      </div>
    </div>
  );
}

function NavButton({ children, disabled, ...props }) {
  return (
    <button
      disabled={disabled}
      className={`
        flex items-center justify-center min-h-[44px] min-w-[44px] sm:min-h-8 sm:min-w-0 sm:h-8 px-1.5 rounded-md transition-colors
        ${disabled
          ? 'text-detec-slate-700 cursor-not-allowed'
          : 'text-detec-slate-400 hover:text-detec-slate-200 hover:bg-detec-slate-800'
        }
      `}
      {...props}
    >
      {children}
    </button>
  );
}

function buildPageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages = [1];
  const left = Math.max(2, current - 1);
  const right = Math.min(total - 1, current + 1);

  if (left > 2) pages.push('...');
  for (let i = left; i <= right; i++) pages.push(i);
  if (right < total - 1) pages.push('...');
  pages.push(total);

  return pages;
}

function ChevronLeftIcon({ className = '' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function ChevronRightIcon({ className = '' }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <polyline points="9 6 15 12 9 18" />
    </svg>
  );
}
