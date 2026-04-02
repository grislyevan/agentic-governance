export default function SectionTabBar({ tabs, activeTab, onChange }) {
  return (
    <div className="flex items-center gap-0 border-b border-detec-edge">
      {tabs.map((tab) => {
        const isActive = tab.key === activeTab;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`
              text-xs font-medium px-3 py-2 transition-colors -mb-px
              ${isActive
                ? 'text-detec-brand border-b-2 border-detec-brand'
                : 'text-detec-ink-secondary hover:text-detec-ink-primary'
              }
            `}
          >
            {tab.label}
            {tab.count != null && (
              <span
                className={`font-data text-data-xs ml-1.5 ${
                  isActive ? 'text-detec-brand/70' : 'text-detec-ink-tertiary'
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
