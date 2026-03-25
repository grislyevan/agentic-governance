export const STORAGE_KEYS = {
  apiUrl: 'detec_api_url',
  apiKey: 'detec_api_key',
  activeTenantId: 'detec_active_tenant_id',
};

export function getActiveTenantId() {
  try { return localStorage.getItem(STORAGE_KEYS.activeTenantId) || null; } catch { return null; }
}

export function setActiveTenantId(id) {
  try {
    if (id == null) {
      localStorage.removeItem(STORAGE_KEYS.activeTenantId);
    } else {
      localStorage.setItem(STORAGE_KEYS.activeTenantId, String(id));
    }
  } catch { /* noop */ }
}

function getStored(key) {
  try { return localStorage.getItem(key) || ''; } catch { return ''; }
}
function removeStored(key) {
  try { localStorage.removeItem(key); } catch { /* noop */ }
}

/** Session tokens are in httpOnly cookies; no token storage in localStorage. */
export function getStoredTokens() {
  return { accessToken: '', refreshToken: '' };
}

/** No-op: tokens are set by the API via Set-Cookie on login/register/refresh. */
export function storeTokens() {}

const _defaultApiBase =
  typeof window !== 'undefined' && window.location?.port === '8000'
    ? '/api'
    : 'http://localhost:8000/api';

/**
 * Call logout endpoint to clear cookies, then clear any local session state.
 * Uses credentials: 'include' so cookies are sent and cleared.
 */
export async function clearTokens() {
  const base = getStored(STORAGE_KEYS.apiUrl) || _defaultApiBase;
  const url = base.replace(/\/+$/, '') + '/auth/logout';
  try {
    await fetch(url, { method: 'POST', credentials: 'include' });
  } catch {
    /* ignore */
  }
  removeStored('detec_access_token');
  removeStored('detec_refresh_token');
  // Also clear in-memory API key on logout (imported lazily to avoid circular dep).
  try {
    const { clearApiKey } = await import('./api');
    clearApiKey();
  } catch { /* noop */ }
}

const DEFAULT_API_URL =
  typeof window !== 'undefined' && window.location?.port === '8000'
    ? '/api'
    : 'http://localhost:8000/api';

/** When not on API port, relative /api would hit the wrong host; use full URL. */
function apiBase() {
  let url = getStored(STORAGE_KEYS.apiUrl) || '';
  if (typeof window !== 'undefined' && window.location?.port !== '8000') {
    if (!url || url === '/api' || url.startsWith('/')) url = DEFAULT_API_URL;
  }
  url = url || DEFAULT_API_URL;
  return url.replace(/\/+$/, '');
}

function authHeaders() {
  const apiKey = getStored(STORAGE_KEYS.apiKey);
  if (apiKey) return { 'X-Api-Key': apiKey };
  return {};
}

function extractDetail(data, fallback) {
  const d = data.detail;
  if (!d) return fallback;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join('; ');
  return JSON.stringify(d);
}

export async function loginRequest(email, password) {
  const res = await fetch(`${apiBase()}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    credentials: 'include',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractDetail(data, `Login failed (${res.status})`));
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function registerRequest(email, password, firstName, lastName, tenantName) {
  const res = await fetch(`${apiBase()}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      first_name: firstName || undefined,
      last_name: lastName || undefined,
      tenant_name: tenantName || undefined,
    }),
    credentials: 'include',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractDetail(data, `Registration failed (${res.status})`));
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function refreshAccessToken() {
  const res = await fetch(`${apiBase()}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    credentials: 'include',
  });
  if (!res.ok) {
    await clearTokens();
    return null;
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function fetchCurrentUser() {
  const headers = authHeaders();
  const res = await fetch(`${apiBase()}/auth/me`, { headers, credentials: 'include' });
  if (!res.ok) return null;
  return res.json();
}

const ROLE_KEY = 'detec_user_role';

/**
 * Returns the current user's role from session storage.
 * Defaults to 'viewer' if not set.
 */
export function getUserRole() {
  try { return sessionStorage.getItem(ROLE_KEY) || 'viewer'; } catch { return 'viewer'; }
}

export function setUserRole(role) {
  try {
    if (role) sessionStorage.setItem(ROLE_KEY, role);
    else sessionStorage.removeItem(ROLE_KEY);
  } catch { /* noop */ }
}
