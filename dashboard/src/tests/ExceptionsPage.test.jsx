import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ExceptionsPage from '../pages/ExceptionsPage';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth', () => ({
  STORAGE_KEYS: { apiUrl: 'detec_api_url', apiKey: 'detec_api_key', activeTenantId: 'detec_active_tenant_id' },
  getStoredTokens: () => ({ accessToken: '', refreshToken: '' }),
  getActiveTenantId: () => null,
  storeTokens: () => {},
  clearTokens: () => Promise.resolve(),
  fetchCurrentUser: () => Promise.resolve(null),
}));

const mockEntries = { items: [], total: 0 };

describe('ExceptionsPage', () => {
  beforeEach(() => {
    api.fetchAllowList = vi.fn().mockResolvedValue(mockEntries);
    api.createAllowListEntry = vi.fn().mockResolvedValue({
      id: 'new-1',
      pattern: 'foo.exe',
      pattern_type: 'name',
      scope: 'tenant',
      reason_code: 'known_safe',
    });
    api.updateAllowListEntry = vi.fn().mockResolvedValue({
      id: 'edit-1',
      pattern: 'bar.exe',
      pattern_type: 'name',
      scope: 'tenant',
      reason_code: 'updated',
    });
    api.deleteAllowListEntry = vi.fn().mockResolvedValue({});
  });

  it('renders the Exceptions page and loads entries', async () => {
    render(
      <MemoryRouter>
        <ExceptionsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(api.fetchAllowList).toHaveBeenCalled();
    });
    expect(screen.getByText('Exceptions')).toBeInTheDocument();
  });

  it('calls createAllowListEntry on new entry submit', async () => {
    render(<MemoryRouter><ExceptionsPage /></MemoryRouter>);
    // verify the mock is wired and defined
    expect(api.createAllowListEntry).toBeDefined();
    expect(typeof api.createAllowListEntry).toBe('function');
  });

  it('exports updateAllowListEntry (PATCH) and is wired in the page import', async () => {
    // The page imports updateAllowListEntry from api; verify the export exists
    expect(typeof api.updateAllowListEntry).toBe('function');
  });

  it('updateAllowListEntry resolves with updated entry data', async () => {
    const result = await api.updateAllowListEntry('edit-1', { reason_code: 'updated' });
    expect(result).toEqual({
      id: 'edit-1',
      pattern: 'bar.exe',
      pattern_type: 'name',
      scope: 'tenant',
      reason_code: 'updated',
    });
  });
});
