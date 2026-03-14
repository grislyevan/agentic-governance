import { getStoredTokens, STORAGE_KEYS } from './auth';

const DEFAULT_API_URL =
  typeof window !== 'undefined' && window.location?.port === '8000'
    ? '/api'
    : 'http://localhost:8000/api';

function getStored(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

/** When not on API port, relative /api would hit the wrong host; use full URL. */
function resolveApiUrl() {
  const stored = getStored(STORAGE_KEYS.apiUrl, '');
  if (typeof window !== 'undefined' && window.location?.port !== '8000') {
    if (!stored || stored === '/api' || stored.startsWith('/')) return DEFAULT_API_URL;
  }
  return stored || DEFAULT_API_URL;
}

export function getApiConfig() {
  return {
    apiUrl: resolveApiUrl(),
    apiKey: getStored(STORAGE_KEYS.apiKey, ''),
  };
}

export function setApiConfig({ apiUrl, apiKey }) {
  try {
    if (apiUrl !== undefined) localStorage.setItem(STORAGE_KEYS.apiUrl, apiUrl);
    if (apiKey !== undefined) localStorage.setItem(STORAGE_KEYS.apiKey, apiKey);
  } catch {
    // localStorage unavailable
  }
}

function buildAuthHeaders() {
  const { accessToken } = getStoredTokens();
  if (accessToken) return { Authorization: `Bearer ${accessToken}` };
  const config = getApiConfig();
  if (config.apiKey) return { 'X-Api-Key': config.apiKey };
  return {};
}

async function apiFetch(path, { apiUrl } = {}) {
  const config = apiUrl ? { apiUrl } : getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}${path}`;
  const headers = buildAuthHeaders();

  const res = await fetch(url, { headers, cache: 'no-store' });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Authentication failed. Check your credentials.');
  }
  if (!res.ok) throw new Error(`API returned ${res.status}`);
  return res.json();
}

export async function fetchDemoStatus() {
  return apiFetch('/demo/status');
}

export async function fetchEndpoints(config, page = 1, pageSize = 200) {
  return apiFetch(`/endpoints?page=${page}&page_size=${pageSize}`, config);
}

export async function updateEndpoint(endpointId, data) {
  return apiMutate('PATCH', `/endpoints/${endpointId}`, data);
}

// Endpoint profiles (tenant-scoped agent profiles)

export async function fetchEndpointProfiles(config, { page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  return apiFetch(`/endpoint-profiles?${params}`, config);
}

export async function fetchEndpointProfile(profileId) {
  return apiFetch(`/endpoint-profiles/${profileId}`);
}

export async function createEndpointProfile(data) {
  return apiMutate('POST', '/endpoint-profiles', data);
}

export async function updateEndpointProfile(profileId, data) {
  return apiMutate('PATCH', `/endpoint-profiles/${profileId}`, data);
}

export async function deleteEndpointProfile(profileId) {
  return apiMutate('DELETE', `/endpoint-profiles/${profileId}`);
}

export async function fetchEndpointStatus(config) {
  return apiFetch('/endpoints/status', config);
}

export async function fetchEvents(config, {
  page = 1,
  pageSize = 500,
  decisionState,
  toolName,
  endpointId,
  observedAfter,
  observedBefore,
  mitreTechnique,
  search,
} = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (decisionState) params.set('decision_state', decisionState);
  if (toolName) params.set('tool_name', toolName);
  if (endpointId) params.set('endpoint_id', endpointId);
  if (observedAfter) params.set('observed_after', observedAfter);
  if (observedBefore) params.set('observed_before', observedBefore);
  if (mitreTechnique) params.set('mitre_technique', mitreTechnique);
  if (search) params.set('search', search);
  return apiFetch(`/events?${params}`, config);
}

export async function fetchAllEvents(config, { observedAfter, observedBefore, endpointId } = {}) {
  const events = [];
  let page = 1;
  const pageSize = 500;

  while (true) {
    const data = await fetchEvents(config, { page, pageSize, observedAfter, observedBefore, endpointId });
    if (data.items) {
      for (const item of data.items) {
        const payload = item.payload && Object.keys(item.payload).length > 0 ? item.payload : {};
        events.push({
          ...payload,
          event_type: payload.event_type ?? item.event_type,
          tool: payload.tool ?? (item.tool_name ? { name: item.tool_name, class: item.tool_class, version: item.tool_version } : null),
          tool_name: item.tool_name ?? payload.tool?.name,
          tool_class: item.tool_class ?? payload.tool?.class,
          decision_state: item.decision_state ?? payload.policy?.decision_state,
          rule_id: item.rule_id ?? payload.policy?.rule_id,
          severity_level: item.severity_level ?? payload.severity?.level,
          observed_at: payload.observed_at ?? item.observed_at,
          endpoint_id: item.endpoint_id ?? payload.endpoint?.id,
        });
      }
    }
    if (page * pageSize >= data.total) break;
    page++;
  }
  return events;
}

export async function fetchAuditLog(config, { page = 1, pageSize = 50, action, resourceType } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (action) params.set('action', action);
  if (resourceType) params.set('resource_type', resourceType);
  return apiFetch(`/audit-log?${params}`, config);
}

export async function fetchPolicies(config, { page = 1, pageSize = 50, category } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (category) params.set('category', category);
  return apiFetch(`/policies?${params}`, config);
}

export async function createPolicy(data) {
  return apiMutate('POST', '/policies', data);
}

export async function updatePolicy(id, data) {
  return apiMutate('PATCH', `/policies/${id}`, data);
}

export async function deletePolicy(id) {
  return apiMutate('DELETE', `/policies/${id}`);
}

export async function restoreDefaultPolicies() {
  return apiMutate('POST', '/policies/restore-defaults');
}

export async function fetchPlaybooks() {
  return apiFetch('/playbooks');
}

export async function fetchPlaybook(id) {
  return apiFetch(`/playbooks/${id}`);
}

export async function createPlaybook(data) {
  return apiMutate('POST', '/playbooks', data);
}

export async function updatePlaybook(id, data) {
  return apiMutate('PUT', `/playbooks/${id}`, data);
}

export async function deletePlaybook(id) {
  return apiMutate('DELETE', `/playbooks/${id}`);
}

export async function testPlaybook(id, eventPayload = {}) {
  return apiMutate('POST', `/playbooks/${id}/test`, { event_payload: eventPayload });
}

export async function fetchPolicyPresets(config) {
  return apiFetch('/policies/presets', config);
}

export async function applyPolicyPreset(presetId) {
  return apiMutate('POST', '/policies/apply-preset', { preset_id: presetId });
}

async function apiMutate(method, path, body) {
  const config = getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}${path}`;
  const headers = { ...buildAuthHeaders(), 'Content-Type': 'application/json' };
  const res = await fetch(url, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Authentication failed. Check your credentials.');
  }
  if (res.status === 204) return null;
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `API returned ${res.status}`);
  }
  return res.json();
}

export async function fetchUsers({ page = 1, perPage = 50, search } = {}) {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (search) params.set('search', search);
  return apiFetch(`/users?${params}`);
}

export async function createUser(data) {
  return apiMutate('POST', '/users', data);
}

export async function updateUser(id, data) {
  return apiMutate('PATCH', `/users/${id}`, data);
}

export async function deleteUser(id) {
  return apiMutate('DELETE', `/users/${id}`);
}

export async function sendInvite({ email, role }) {
  const localPart = (email || '').split('@')[0] || 'User';
  const first_name = localPart.charAt(0).toUpperCase() + localPart.slice(1).replace(/[^a-zA-Z0-9]/g, '') || 'User';
  return apiMutate('POST', '/users', {
    first_name,
    last_name: null,
    email: email.trim(),
    role: role || 'analyst',
  });
}

// SSO

export async function fetchSsoStatus() {
  const config = getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}/auth/sso/status`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`SSO status failed (${res.status})`);
  return res.json();
}

export async function ssoCallback(code, state) {
  const config = getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}/auth/sso/callback`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, state }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `SSO callback failed (${res.status})`);
  }
  return res.json();
}

// Auth: password reset + invite flows (unauthenticated)

export async function forgotPassword(email) {
  return apiMutatePublic('POST', '/auth/forgot-password', { email });
}

export async function resetPassword(token, newPassword) {
  return apiMutatePublic('POST', '/auth/reset-password', { token, new_password: newPassword });
}

export async function acceptInvite(token, newPassword) {
  return apiMutatePublic('POST', '/auth/accept-invite', { token, new_password: newPassword });
}

async function apiMutatePublic(method, path, body) {
  const config = getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}${path}`;
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

// Server settings (TCP gateway; admin can view, owner can update)

export async function fetchServerSettings() {
  return apiFetch('/server/settings');
}

export async function updateServerSettings(body) {
  return apiMutate('PUT', '/server/settings', body);
}

// Agent download (uses JWT auth; server embeds tenant agent key automatically)

export async function downloadAgent({ platform, interval, protocol }) {
  const config = getApiConfig();
  const params = new URLSearchParams({ platform });
  if (interval) params.set('interval', interval);
  if (protocol) params.set('protocol', protocol);
  const url = `${config.apiUrl.replace(/\/+$/, '')}/agent/download?${params}`;

  const headers = buildAuthHeaders();

  const res = await fetch(url, { headers });
  if (res.status === 404) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'No pre-built package available for this platform.');
  }
  if (res.status === 401 || res.status === 403) {
    throw new Error('Authentication failed. Admin or owner role is required.');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Download failed (${res.status})`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `detec-agent-${platform}.zip`;

  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

export async function enrollAgentByEmail({ email, platform, interval, protocol }) {
  return apiMutate('POST', '/agent/enroll-email', { email, platform, interval, protocol });
}

// EDR enforcement config

export async function fetchEDRStatus(endpointId) {
  return apiFetch(`/enforcement/endpoints/${endpointId}/edr-status`);
}

export async function updateEDRConfig(endpointId, data) {
  return apiMutate('PUT', `/enforcement/endpoints/${endpointId}/edr-config`, data);
}

export async function testEDRConnectivity(endpointId) {
  return apiMutate('POST', `/enforcement/edr-test/${endpointId}`);
}

export async function fetchPostureSummary() {
  return apiFetch('/enforcement/posture-summary');
}

export async function updateEndpointPosture(endpointId, { enforcement_posture, auto_enforce_threshold }) {
  return apiMutate('PUT', `/enforcement/endpoints/${endpointId}/posture`, {
    enforcement_posture,
    auto_enforce_threshold,
  });
}

export async function updateTenantPosture({ enforcement_posture, auto_enforce_threshold }) {
  return apiMutate('PUT', '/enforcement/tenant-posture', {
    enforcement_posture,
    auto_enforce_threshold,
  });
}

export async function fetchAllowList() {
  return apiFetch('/enforcement/allow-list');
}

export async function addAllowListEntry({ pattern, pattern_type, description }) {
  return apiMutate('POST', '/enforcement/allow-list', {
    pattern,
    pattern_type,
    description,
  });
}

export async function deleteAllowListEntry(entryId) {
  return apiMutate('DELETE', `/enforcement/allow-list/${entryId}`);
}

// Disabled services (anti-resurrection recovery)

export async function fetchDisabledServices(endpointId) {
  const params = endpointId ? `?endpoint_id=${endpointId}` : '';
  return apiFetch(`/enforcement/disabled-services${params}`);
}

export async function restoreServices(endpointId, serviceIds = []) {
  return apiMutate('POST', '/enforcement/restore-services', {
    endpoint_id: endpointId,
    service_ids: serviceIds,
  });
}

// Webhooks

export async function fetchWebhooks() {
  return apiFetch('/webhooks');
}

export async function fetchWebhookTemplates() {
  return apiFetch('/webhooks/templates');
}

export async function createWebhook(data) {
  return apiMutate('POST', '/webhooks', data);
}

export async function createWebhookFromTemplate(templateId, config) {
  return apiMutate('POST', '/webhooks/from-template', {
    template_id: templateId,
    config,
  });
}

export async function updateWebhook(id, data) {
  return apiMutate('PATCH', `/webhooks/${id}`, data);
}

export async function deleteWebhook(id) {
  return apiMutate('DELETE', `/webhooks/${id}`);
}

export async function testWebhook(id) {
  return apiMutate('POST', `/webhooks/${id}/test`);
}

// Billing

export async function fetchBillingStatus() {
  return apiFetch('/billing/status');
}

export async function fetchBillingTiers() {
  return apiFetch('/billing/tiers');
}

export async function createCheckoutSession({ tier, successUrl, cancelUrl }) {
  return apiMutate('POST', '/billing/checkout', {
    tier,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
}

export async function createPortalSession({ returnUrl }) {
  return apiMutate('POST', '/billing/portal', {
    return_url: returnUrl,
  });
}

// Compliance reports

export async function generateComplianceReport(startDate, endDate, format) {
  const config = getApiConfig();
  const url = `${config.apiUrl.replace(/\/+$/, '')}/reports/compliance`;
  const headers = { ...buildAuthHeaders(), 'Content-Type': 'application/json' };
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ start_date: startDate, end_date: endDate, format }),
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error('Authentication failed. Check your credentials.');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `API returned ${res.status}`);
  }
  if (format === 'json') {
    return res.json();
  }
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `detec-compliance-${startDate}-${endDate}.${format}`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
  return { downloaded: true };
}

export async function fetchComplianceSummary() {
  return apiFetch('/reports/compliance/summary');
}

// Data flow

export async function fetchDataFlowSummary(days = 7) {
  return apiFetch(`/data-flow/summary?days=${days}`);
}

// Tenants (organizations)

export async function fetchCurrentTenant() {
  return apiFetch('/tenants/current');
}

export async function fetchMyTenants() {
  return apiFetch('/tenants/mine');
}

export async function createTenant(name) {
  return apiMutate('POST', '/tenants', { name });
}

export async function updateTenant(id, data) {
  return apiMutate('PATCH', `/tenants/${id}`, data);
}

export async function switchTenant(tenantId) {
  return apiMutate('POST', '/tenants/switch', { tenant_id: tenantId });
}
