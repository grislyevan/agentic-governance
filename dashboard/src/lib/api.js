import { getStoredTokens, STORAGE_KEYS } from './auth';

function getStored(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

export function getApiConfig() {
  return {
    apiUrl: getStored(STORAGE_KEYS.apiUrl, '/api'),
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

export async function fetchEndpoints(config, page = 1, pageSize = 200) {
  return apiFetch(`/endpoints?page=${page}&page_size=${pageSize}`, config);
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
  search,
} = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (decisionState) params.set('decision_state', decisionState);
  if (toolName) params.set('tool_name', toolName);
  if (endpointId) params.set('endpoint_id', endpointId);
  if (observedAfter) params.set('observed_after', observedAfter);
  if (observedBefore) params.set('observed_before', observedBefore);
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
        events.push(item.payload && Object.keys(item.payload).length > 0 ? item.payload : item);
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

export async function fetchPolicies(config, { page = 1, pageSize = 50 } = {}) {
  return apiFetch(`/policies?page=${page}&page_size=${pageSize}`, config);
}

export async function createPolicy(data) {
  return apiMutate('POST', '/policies', data);
}

export async function updatePolicy(id, data) {
  return apiMutate('PATCH', `/policies/${id}`, data);
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
