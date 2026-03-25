import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import MembersPage from '../pages/MembersPage';
import * as api from '../lib/api';

vi.mock('../lib/api');
vi.mock('../lib/auth', () => ({
  getStoredTokens: () => ({ accessToken: 'fake' }),
  getUserRole: () => 'owner',
  getCurrentUserId: () => 'u-owner',
}));

const mockUsers = {
  items: [
    { id: 'u-owner', email: 'owner@co.com', role: 'owner', first_name: 'Alice', last_name: 'O', is_active: true },
    { id: 'u-admin', email: 'admin@co.com', role: 'admin', first_name: 'Bob', last_name: 'A', is_active: true },
  ],
  total: 2, page: 1, per_page: 50,
};

describe('MembersPage', () => {
  beforeEach(() => {
    api.fetchUsers = vi.fn().mockResolvedValue(mockUsers);
    api.createUser = vi.fn().mockResolvedValue({ id: 'u-new', email: 'new@co.com', role: 'analyst', is_active: true });
    api.updateUser = vi.fn().mockResolvedValue({ id: 'u-admin', role: 'analyst' });
    api.deactivateUser = vi.fn().mockResolvedValue({ id: 'u-admin', is_active: false });
  });

  it('renders member list', async () => {
    render(<MembersPage />);
    await waitFor(() => expect(screen.getByText('owner@co.com')).toBeInTheDocument());
    expect(screen.getByText('admin@co.com')).toBeInTheDocument();
  });

  it('cannot deactivate the last owner', async () => {
    api.fetchUsers = vi.fn().mockResolvedValue({
      ...mockUsers, items: [mockUsers.items[0]], total: 1,
    });
    render(<MembersPage />);
    await waitFor(() => screen.getByText('owner@co.com'));
    expect(screen.queryAllByRole('button', { name: /deactivate/i })).toHaveLength(0);
  });

  it('calls deactivateUser on confirm', async () => {
    render(<MembersPage />);
    await waitFor(() => screen.getByText('admin@co.com'));
    const deactivateBtn = screen.getAllByRole('button', { name: /deactivate/i })[0];
    await userEvent.click(deactivateBtn);
    const confirmBtn = await screen.findByRole('button', { name: /confirm/i });
    await userEvent.click(confirmBtn);
    expect(api.deactivateUser).toHaveBeenCalledWith('u-admin');
  });
});
