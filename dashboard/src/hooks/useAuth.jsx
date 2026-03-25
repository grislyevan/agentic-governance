import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchCurrentUser,
  loginRequest,
  registerRequest,
  refreshAccessToken,
  clearTokens,
  getStoredTokens,
  getActiveTenantId,
} from '../lib/auth';

const AuthContext = createContext(null);

const TOKEN_REFRESH_INTERVAL = 4 * 60 * 1000; // 4 minutes

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer = useRef(null);
  const refreshing = useRef(false);

  const startRefreshTimer = useCallback(() => {
    if (refreshTimer.current) clearInterval(refreshTimer.current);
    refreshTimer.current = setInterval(async () => {
      if (refreshing.current) return;
      refreshing.current = true;
      try {
        const result = await refreshAccessToken();
        if (!result) {
          setUser(null);
          clearInterval(refreshTimer.current);
        }
      } finally {
        refreshing.current = false;
      }
    }, TOKEN_REFRESH_INTERVAL);
  }, []);

  const hydrate = useCallback(async () => {
    setLoading(true);
    try {
      const userData = await fetchCurrentUser();
      if (userData) {
        const storedTenantId = getActiveTenantId();
        setUser({
          ...userData,
          activeTenantId: storedTenantId ?? userData.tenant_id ?? null,
        });
        const { accessToken } = getStoredTokens();
        if (accessToken) startRefreshTimer();
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [startRefreshTimer]);

  useEffect(() => {
    hydrate();
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, [hydrate]);

  const login = useCallback(async (email, password) => {
    const tokens = await loginRequest(email, password);
    const userData = await fetchCurrentUser();
    const storedTenantId = getActiveTenantId();
    const enriched = { ...userData, activeTenantId: storedTenantId ?? userData?.tenant_id ?? null };
    setUser(enriched);
    startRefreshTimer();
    return { tokens, user: enriched };
  }, [startRefreshTimer]);

  const register = useCallback(async (email, password, firstName, lastName, tenantName) => {
    const tokens = await registerRequest(email, password, firstName, lastName, tenantName);
    const userData = await fetchCurrentUser();
    const storedTenantId = getActiveTenantId();
    const enriched = { ...userData, activeTenantId: storedTenantId ?? userData?.tenant_id ?? null };
    setUser(enriched);
    startRefreshTimer();
    return { tokens, user: enriched };
  }, [startRefreshTimer]);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    if (refreshTimer.current) clearInterval(refreshTimer.current);
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refresh: hydrate,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export default function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
