import ToolRow from './ToolRow';

const COLUMNS = [
  { label: 'Tool', className: 'w-[180px] sm:w-[220px]' },
  { label: 'Confidence', className: 'w-[100px] sm:w-[120px]' },
  { label: 'Detected policy', className: 'hidden md:table-cell' },
  { label: 'Triggered signal', className: 'hidden lg:table-cell' },
  { label: 'Actions', className: 'w-[200px] lg:w-[260px]' },
  { label: '', className: 'w-10' },
];

export default function ToolsTable({ tools }) {
  if (tools.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-detec-slate-700 bg-detec-slate-800/30 px-8 py-16 text-center">
        <div className="mb-3 opacity-40">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#14b8a6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>
        <div className="text-detec-teal-500/80 text-sm font-medium mb-1">All clear</div>
        <div className="text-detec-slate-600 text-sm max-w-xs mx-auto">
          No agentic tools detected in this view.
          Adjust your filters, or connect an endpoint agent to start scanning.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-detec-slate-700/50 overflow-x-auto overflow-hidden">
      <table className="w-full text-left min-w-[640px]" aria-label="Detected tools">
        <thead>
          <tr className="bg-detec-slate-800/80 border-b border-detec-slate-700/50">
            {COLUMNS.map((col, i) => (
              <th
                key={i}
                className={`px-4 py-3 text-xs font-medium text-detec-slate-500 uppercase tracking-wider ${col.className}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tools.map((tool, i) => (
            <ToolRow key={`${tool.name}-${i}`} tool={tool} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
