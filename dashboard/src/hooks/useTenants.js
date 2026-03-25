import { useState, useEffect } from 'react';
import useAuth from './useAuth';
import { fetchTenants } from '../lib/api';

/**
 * Fetches the list of tenants the authenticated user belongs to.
 * Only triggers when the user is authenticated.
 */
export default function useTenants() {
  const { isAuthenticated } = useAuth();
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTenants()
      .then((data) => {
        if (!cancelled) {
          setTenants(data?.items ?? []);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [isAuthenticated]);

  return { tenants, loading, error };
}
