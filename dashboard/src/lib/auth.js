export const STORAGE_KEYS = {
  accessToken: 'detec_access_token',
  refreshToken: 'detec_refresh_token',
  apiUrl: 'detec_api_url',
  apiKey: 'detec_api_key',
};

function getStored(key) {
  try { return localStorage.getItem(key) || ''; } catch { return ''; }
}
function setStored(key, value) {
  try { localStorage.setItem(key, value); } catch { /* noop */ }
}
function removeStored(key) {
  try { localStorage.removeItem(key); } catch { /* noop */ }
}

export function getStoredTokens() {
  return {
    accessToken: getStored(STORAGE_KEYS.accessToken),
    refreshToken: getStored(STORAGE_KEYS.refreshToken),
  };
}

export function storeTokens({ access_token, refresh_token }) {
  setStored(STORAGE_KEYS.accessToken, access_token);
  setStored(STORAGE_KEYS.refreshToken, refresh_token);
}

export function clearTokens() {
  removeStored(STORAGE_KEYS.accessToken);
  removeStored(STORAGE_KEYS.refreshToken);
}

function apiBase() {
  const url = getStored(STORAGE_KEYS.apiUrl) || 'http://localhost:8000';
  return url.replace(/\/+$/, '');
}

function authHeaders() {
  const { accessToken } = getStoredTokens();
  if (accessToken) return { Authorization: `Bearer ${accessToken}` };
  const apiKey = getStored(STORAGE_KEYS.apiKey);
  if (apiKey) return { 'X-Api-Key': apiKey };
  return {};
}

export async function loginRequest(email, password) {
  const res = await fetch(`${apiBase()}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Login failed (${res.status})`);
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function registerRequest(email, password, fullName, tenantName) {
  const res = await fetch(`${apiBase()}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      full_name: fullName || undefined,
      tenant_name: tenantName || undefined,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Registration failed (${res.status})`);
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function refreshAccessToken() {
  const { refreshToken } = getStoredTokens();
  if (!refreshToken) return null;

  const res = await fetch(`${apiBase()}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const data = await res.json();
  storeTokens(data);
  return data;
}

export async function fetchCurrentUser() {
  const headers = authHeaders();
  if (!headers.Authorization && !headers['X-Api-Key']) return null;

  const res = await fetch(`${apiBase()}/auth/me`, { headers });
  if (!res.ok) return null;
  return res.json();
}
