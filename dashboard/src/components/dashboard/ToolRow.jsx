import { useState, useRef, useEffect } from 'react';
import { severityLabel } from '../../parseNdjson';
import CopyToast, { useCopyToast } from './CopyToast';

const CONFIDENCE_COLORS = {
  High: '#14b8a6',
  Medium: '#f59e0b',
  Low: '#94a3b8',
};

const DECISION_STYLES = {
  block:             { bg: 'bg-detec-enforce-block/15',    text: 'text-detec-enforce-block',    border: 'border-detec-enforce-block/30',    label: 'LOCKED' },
  approval_required: { bg: 'bg-detec-enforce-approval/15', text: 'text-detec-enforce-approval', border: 'border-detec-enforce-approval/30', label: 'APPROVAL REQUIRED' },
  warn:              { bg: 'bg-detec-enforce-warn/15',     text: 'text-detec-enforce-warn',     border: 'border-detec-enforce-warn/30',     label: 'WARNED' },
  detect:            { bg: 'bg-detec-enforce-detect/15',   text: 'text-detec-enforce-detect',   border: 'border-detec-enforce-detect/30',   label: 'DETECTED' },
};

const CONFIDENCE_STYLES = {
  High:   'text-detec-confidence-high',
  Medium: 'text-detec-confidence-medium',
  Low:    'text-detec-confidence-low',
};

const TOOL_ICONS = {
  'Cursor':             '🖱️',
  'Claude Code':        '🤖',
  'Ollama':             '🦙',
  'Copilot':            '✈️',
  'Open Interpreter':   '🔮',
  'LM Studio':          '🧠',
  'Aider':              '🛠️',
  'Continue':           '▶️',
  'OpenClaw':           '🦀',
  'GPT-Pilot':          '🚀',
  'Cline':              '📎',
  'Claude Cowork':      '👥',
};

const DECISION_ROUTES = {
  block: 'events',
  approval_required: 'approvals',
  warn: 'events',
  detect: 'events',
};

export default function ToolRow({ tool, onNavigate }) {
  const [expanded, setExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const ds = DECISION_STYLES[tool.decision_state] || DECISION_STYLES.detect;
  const confStyle = CONFIDENCE_STYLES[tool.confidenceBand] || 'text-detec-ui-muted';
  const icon = TOOL_ICONS[tool.name] || '🔧';

  const policyTime = tool.observed_at
    ? new Date(tool.observed_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : '';

  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [menuOpen]);

  const { copied, copy } = useCopyToast();

  const handleCopyName = () => {
    copy(tool.name);
    setMenuOpen(false);
  };

  const handleCopyDetails = () => {
    const details = [
      `Tool: ${tool.name}`,
      `Class: ${tool.class}`,
      `Decision: ${tool.policyLabel}`,
      `Confidence: ${tool.confidenceBand}`,
      tool.severity_level ? `Severity: ${tool.severity_level}` : null,
      tool.observed_at ? `Observed: ${new Date(tool.observed_at).toLocaleString()}` : null,
    ].filter(Boolean).join('\n');
    copy(details);
    setMenuOpen(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setExpanded(!expanded);
    }
  };

  return (
    <>
      <tr
        onClick={() => setExpanded(!expanded)}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-expanded={expanded}
        className={`
          border-b border-detec-ui-border/40 cursor-pointer transition-colors
          ${expanded ? 'bg-detec-ui-surface/80' : 'hover:bg-detec-ui-surface/40'}
          focus:outline-none focus:ring-1 focus:ring-detec-ui-accent/50 focus:ring-inset
        `}
      >
        <td className="px-3 sm:px-4 py-3">
          <div className="flex items-center gap-2 sm:gap-2.5">
            <span className="w-8 h-8 rounded-lg bg-detec-ui-surface border border-detec-ui-border flex items-center justify-center text-sm">
              {icon}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-detec-ui-text">{tool.name}</span>
                {copied && <CopyToast />}
              </div>
              {tool.version && (
                <div className="text-xs text-detec-ui-muted font-mono">{tool.version}</div>
              )}
            </div>
          </div>
        </td>

        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: CONFIDENCE_COLORS[tool.confidenceBand] || '#94a3b8' }} />
            <span className={`text-sm font-medium ${confStyle}`}>
              {tool.confidenceBand}
            </span>
          </div>
        </td>

        <td className="px-3 sm:px-4 py-3 hidden md:table-cell">
          <div className="text-sm text-detec-ui-text">
            {tool.rule_id || tool.policyLabel}
            {policyTime && (
              <span className="text-detec-ui-muted"> at {policyTime}</span>
            )}
          </div>
          {tool.severity_level && (
            <span className={`text-xs font-mono ${severityColor(tool.severity_level)}`}>
              {tool.severity_level} {severityLabel(tool.severity_level)}
            </span>
          )}
        </td>

        <td className="px-3 sm:px-4 py-3 hidden lg:table-cell">
          <div className="text-sm text-detec-ui-muted">
            {tool.summary || (tool.reason_codes?.length ? tool.reason_codes[0] : 'N/A')}
          </div>
          {tool.observed_at && (
            <div className="text-xs text-detec-ui-muted">
              at {new Date(tool.observed_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
            </div>
          )}
        </td>

        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                const route = DECISION_ROUTES[tool.decision_state] || 'events';
                onNavigate?.(route);
              }}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border hover:ring-1 hover:ring-current/30 transition-all ${ds.bg} ${ds.text} ${ds.border}`}
              title={`View ${ds.label.toLowerCase()} details`}
            >
              {ds.label}
            </button>
            <span className="text-xs text-detec-ui-muted max-w-[180px] truncate">
              {tool.summary || ''}
            </span>
          </div>
        </td>

        <td className="px-2 sm:px-3 py-3">
          <div className="relative" ref={menuRef}>
            <button
              onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
              className="p-1 text-detec-ui-muted hover:text-detec-ui-text rounded transition-colors"
              aria-label="Row actions"
              aria-haspopup="true"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="12" cy="5" r="1.5" />
                <circle cx="12" cy="12" r="1.5" />
                <circle cx="12" cy="19" r="1.5" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-detec-ui-surface border border-detec-ui-border rounded-lg shadow-lg py-1 z-50">
                <button
                  onClick={(e) => { e.stopPropagation(); setExpanded(true); setMenuOpen(false); }}
                  className="w-full text-left px-3 py-2 text-sm text-detec-ui-text hover:bg-detec-slate-700/50 transition-colors"
                >
                  View details
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleCopyName(); }}
                  className="w-full text-left px-3 py-2 text-sm text-detec-ui-text hover:bg-detec-slate-700/50 transition-colors"
                >
                  Copy tool name
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleCopyDetails(); }}
                  className="w-full text-left px-3 py-2 text-sm text-detec-ui-text hover:bg-detec-slate-700/50 transition-colors"
                >
                  Copy full details
                </button>
              </div>
            )}
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="bg-detec-slate-800">
          <td colSpan={6} className="px-4 py-3">
            <div className="flex flex-wrap gap-6 text-sm">
              {tool.enforcement_applied && (
                <DetailItem label="Enforcement applied">
                  <span className={`${ds.text} font-medium`}>
                    {tool.enforcement_applied.replace(/_/g, ' ')}
                  </span>
                </DetailItem>
              )}
              {tool.reason_codes?.length > 0 && (
                <DetailItem label="Reason codes">
                  <span className="font-mono text-xs text-detec-ui-muted">
                    {tool.reason_codes.join(' · ')}
                  </span>
                </DetailItem>
              )}
              {tool.summary && (
                <DetailItem label="Action summary">
                  {tool.summary}
                </DetailItem>
              )}
              {tool.observed_at && (
                <DetailItem label="Observed">
                  {new Date(tool.observed_at).toLocaleString()}
                </DetailItem>
              )}
              <DetailItem label="Tool class">
                Class {tool.class}
              </DetailItem>
              {tool.attribution_confidence != null && (
                <DetailItem label="Raw confidence">
                  {Math.round(tool.attribution_confidence * 100)}%
                </DetailItem>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function DetailItem({ label, children }) {
  return (
    <div className="min-w-[140px]">
      <div className="text-xs text-detec-ui-muted uppercase tracking-wider font-medium mb-0.5">
        {label}
      </div>
      <div className="text-detec-ui-text">{children}</div>
    </div>
  );
}

function severityColor(level) {
  const map = {
    S0: 'text-detec-ui-muted',
    S1: 'text-detec-enforce-warn',
    S2: 'text-detec-enforce-approval',
    S3: 'text-detec-enforce-block',
    S4: 'text-detec-enforce-block font-bold',
  };
  return map[level] || 'text-detec-ui-muted';
}
