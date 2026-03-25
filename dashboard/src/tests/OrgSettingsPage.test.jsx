import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import OrgSettingsPage from '../pages/OrgSettingsPage';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth', () => ({
  getStoredTokens: () => ({ accessToken: 'fake' }),
  getUserRole: () => 'owner',
}));

const mockTenant = {
  id: 't1', name: 'Acme', slug: 'acme',
  subscription_tier: 'pro', member_count: 3, endpoint_count: 5, role: 'owner',
};

describe('OrgSettingsPage', () => {
  beforeEach(() => {
    api.fetchCurrentTenant = vi.fn().mockResolvedValue(mockTenant);
    api.updateTenant = vi.fn().mockResolvedValue({ id: 't1', name: 'Acme Corp', slug: 'acme-corp' });
  });

  it('displays tenant details', async () => {
    render(<OrgSettingsPage />);
    await waitFor(() => expect(screen.getByText('Acme')).toBeInTheDocument());
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows edit button for owner', async () => {
    render(<OrgSettingsPage />);
    await waitFor(() => screen.getByText('Acme'));
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('hides edit button for non-owner', async () => {
    api.fetchCurrentTenant = vi.fn().mockResolvedValue({ ...mockTenant, role: 'analyst' });
    render(<OrgSettingsPage />);
    await waitFor(() => screen.getByText('Acme'));
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
  });

  it('calls updateTenant on save', async () => {
    render(<OrgSettingsPage />);
    await waitFor(() => screen.getByText('Acme'));
    await userEvent.click(screen.getByRole('button', { name: /edit/i }));
    await userEvent.clear(screen.getByLabelText(/org name/i));
    await userEvent.type(screen.getByLabelText(/org name/i), 'Acme Corp');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(api.updateTenant).toHaveBeenCalledWith('t1', { name: 'Acme Corp' });
  });
});
