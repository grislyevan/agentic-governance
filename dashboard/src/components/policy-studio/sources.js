/**
 * Endpoint-native source catalog for Policy Studio (v1).
 * Future connectors (M365, Google, GitHub, Datadog) are documented in the spec as post-v1.
 */

export const ENDPOINT_SOURCES = [
  {
    id: 'local_agent',
    name: 'Local agent / IDE & CLI',
    description: 'Tools and processes on this endpoint (Cursor, Copilot, Claude Code, etc.)',
    tags: ['IDE', 'CLI'],
  },
  {
    id: 'git',
    name: 'Git / version control',
    description: 'Commits, branches, remotes, and repo visibility',
    tags: ['Git', 'Repos'],
  },
  {
    id: 'filesystem',
    name: 'Filesystem paths',
    description: 'Local and mounted paths, file types',
    tags: ['Filesystem', 'Files'],
  },
  {
    id: 'network',
    name: 'Outbound network',
    description: 'Connections and destinations',
    tags: ['Network'],
  },
  {
    id: 'container',
    name: 'Container / runtime',
    description: 'Containers and runtime environments',
    tags: ['Container'],
  },
];

export const SCOPE_CHIPS = [
  { id: 'files', label: 'Files' },
  { id: 'messages', label: 'Messages' },
  { id: 'repositories', label: 'Repositories' },
  { id: 'credentials', label: 'Credentials' },
  { id: 'api_keys', label: 'API keys' },
  { id: 'pii', label: 'PII' },
  { id: 'source_code', label: 'Source code' },
  { id: 'customer_data', label: 'Customer data' },
];

export const OUTCOME_OPTIONS = [
  { value: 'detect', label: 'Detect only' },
  { value: 'warn', label: 'Warn' },
  { value: 'approval_required', label: 'Require approval' },
  { value: 'block', label: 'Block' },
];

export const SEVERITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];
