/**
 * useApiRequest — a generic hook for async API calls with consistent
 * loading, error, and refetch state.
 *
 * Features:
 *   - Centralised 401 handling → calls logout() and redirects to login
 *   - Network-error normalisation to user-friendly strings
 *   - `loading` starts true on mount (or when deps change) to avoid flash
 *   - `refetch()` re-runs the request on demand
 *   - Optional `skip` flag to defer the first fetch (useful for auth guards)
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApiRequest(
 *     () => fetchEvents({ page: 1 }),
 *     [page]
 *   );
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import useAuth from './useAuth';

/**
 * Normalise an error thrown by apiFetch / apiMutate into a display string.
 * Handles FastAPI error detail objects, plain strings, and network failures.
 */
function normaliseError(err) {
  if (!err) return 'An unexpected error occurred.';
  // HTTP errors from apiFetch throw with a `status` property
  if (err.status === 401 || err.status === 403) {
    return null; // caller handles auth errors — useApiRequest redirects
  }
  if (err.status === 404) return 'Resource not found.';
  if (err.status === 422) return 'Validation error: ' + (err.message || 'invalid request.');
  if (err.status >= 500) return 'Server error. Please try again in a moment.';
  // Network / fetch failures
  if (err instanceof TypeError && err.message.includes('fetch')) {
    return 'Network error — check your connection.';
  }
  return err.message || String(err) || 'An unexpected error occurred.';
}

/**
 * @param {() => Promise<any>} requestFn  Async function that returns data.
 * @param {any[]} [deps=[]]               Dependency array — re-runs when these change.
 * @param {{ skip?: boolean }} [opts={}]  Options.
 */
export default function useApiRequest(requestFn, deps = [], opts = {}) {
  const { logout } = useAuth();
  const { skip = false } = opts;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState(null);

  // Keep a stable ref to requestFn to avoid infinite loops when the caller
  // passes an inline function without memoising it.
  const requestRef = useRef(requestFn);
  requestRef.current = requestFn;

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await requestRef.current();
      setData(result);
    } catch (err) {
      // Redirect on auth failure
      if (err && (err.status === 401 || err.status === 403)) {
        if (logout) logout();
        return;
      }
      const msg = normaliseError(err);
      if (msg) setError(msg);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (skip) return;
    execute();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execute, skip]);

  return { data, loading, error, refetch: execute };
}
