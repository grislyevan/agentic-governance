/**
 * Tests for the useApiRequest hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

// ------------------------------------------------------------------
// Mock useAuth so we can control the logout callback
// ------------------------------------------------------------------
const mockLogout = vi.fn();

vi.mock('../hooks/useAuth', () => ({
  default: () => ({ logout: mockLogout }),
}));

import useApiRequest from '../hooks/useApiRequest';

describe('useApiRequest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns data on successful request', async () => {
    const requestFn = vi.fn().mockResolvedValue({ items: [1, 2, 3] });
    const { result } = renderHook(() => useApiRequest(requestFn));

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual({ items: [1, 2, 3] });
    expect(result.current.error).toBeNull();
    expect(requestFn).toHaveBeenCalledTimes(1);
  });

  it('sets error on request failure', async () => {
    const err = new Error('Network error');
    const requestFn = vi.fn().mockRejectedValue(err);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe('Network error');
  });

  it('calls logout and does not set error on 401', async () => {
    const authErr = Object.assign(new Error('Unauthorized'), { status: 401 });
    const requestFn = vi.fn().mockRejectedValue(authErr);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBeNull();
  });

  it('calls logout and does not set error on 403', async () => {
    const authErr = Object.assign(new Error('Forbidden'), { status: 403 });
    const requestFn = vi.fn().mockRejectedValue(authErr);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBeNull();
  });

  it('does not make initial request when skip=true', async () => {
    const requestFn = vi.fn().mockResolvedValue({ items: [] });
    const { result } = renderHook(() =>
      useApiRequest(requestFn, [], { skip: true })
    );

    // Should not be loading and no call
    expect(result.current.loading).toBe(false);
    expect(requestFn).not.toHaveBeenCalled();
  });

  it('refetch re-runs the request', async () => {
    const requestFn = vi.fn()
      .mockResolvedValueOnce({ items: [1] })
      .mockResolvedValueOnce({ items: [1, 2] });

    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ items: [1] });

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.data).toEqual({ items: [1, 2] });
    expect(requestFn).toHaveBeenCalledTimes(2);
  });

  it('normalises network TypeError to a friendly message', async () => {
    const netErr = new TypeError('Failed to fetch');
    const requestFn = vi.fn().mockRejectedValue(netErr);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toContain('Network error');
  });

  it('normalises 404 to a resource not found message', async () => {
    const err = Object.assign(new Error('Not Found'), { status: 404 });
    const requestFn = vi.fn().mockRejectedValue(err);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toContain('not found');
  });

  it('normalises 500 to a server error message', async () => {
    const err = Object.assign(new Error('Internal Server Error'), { status: 500 });
    const requestFn = vi.fn().mockRejectedValue(err);
    const { result } = renderHook(() => useApiRequest(requestFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toContain('Server error');
  });
});
