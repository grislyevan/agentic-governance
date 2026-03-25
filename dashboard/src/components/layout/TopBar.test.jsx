import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TopBar from './TopBar';

// ── API mocks ─────────────────────────────────────────────────────────────────
vi.mock('../../lib/api', () => ({
  switchTenant: vi.fn(),
  fetchTenants: vi.fn(),
}));

// ── auth lib mock ─────────────────────────────────────────────────────────────
vi.mock('../../lib/auth', () => ({
  setActiveTenantId: vi.fn(),
  getActiveTenantId: vi.fn(() => 't1'),
  getStoredTokens: vi.fn(() => ({ accessToken: '', refreshToken: '' })),
  clearTokens: vi.fn(),
  fetchCurrentUser: vi.fn(),
  loginRequest: vi.fn(),
  registerRequest: vi.fn(),
  refreshAccessToken: vi.fn(),
  storeTokens: vi.fn(),
}));

// ── Auth hook mock ────────────────────────────────────────────────────────────
vi.mock('../../hooks/useAuth', () => ({
  default: () => ({
    user: { id: 'u1', tenant_id: 't1', activeTenantId: 't1', role: 'admin', email: 'admin@test.com' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// ── useTenants mock — controlled via module-level variable ────────────────────
// We mock the hook directly so tests can control what tenant list it returns
// without needing to mock the async fetchTenants and wait for useEffect.
let _mockTenants = [];
vi.mock('../../hooks/useTenants', () => ({
  default: () => ({ tenants: _mockTenants, loading: false, error: null }),
}));

// ── Suppress window.location.reload ──────────────────────────────────────────
const reloadMock = vi.fn();
Object.defineProperty(window, 'location', {
  configurable: true,
  writable: true,
  value: { reload: reloadMock },
});

// ── Test data ─────────────────────────────────────────────────────────────────
const SINGLE_TENANT = [{ id: 't1', name: 'Acme Corp', role: 'admin' }];
const MULTI_TENANTS = [
  { id: 't1', name: 'Acme Corp', role: 'admin' },
  { id: 't2', name: 'Beta Ltd', role: 'member' },
  { id: 't3', name: 'Gamma Inc', role: 'viewer' },
];

import * as api from '../../lib/api';
import * as authLib from '../../lib/auth';

function renderTopBar() {
  api.switchTenant.mockResolvedValue({});
  return render(
    <TopBar
      activePage="endpoints"
      onNavigate={vi.fn()}
      onSearch={vi.fn()}
      onRefresh={vi.fn()}
      alertCount={0}
      onMenuClick={vi.fn()}
    />
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('TopBar — OrgSwitcher with single tenant', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _mockTenants = SINGLE_TENANT;
  });

  it('shows tenant name as static text (not a switcher button) when only one tenant exists', () => {
    renderTopBar();

    // With a single tenant, the component renders a <span> not a switcher button
    expect(screen.queryByRole('button', { name: /switch organisation/i })).not.toBeInTheDocument();
    // The tenant name is present
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });
});

describe('TopBar — OrgSwitcher with multiple tenants', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _mockTenants = MULTI_TENANTS;
    reloadMock.mockReset();
  });

  it('renders a switcher button with the active tenant name', () => {
    renderTopBar();

    const switcher = screen.getByRole('button', { name: /switch organisation/i });
    expect(switcher).toBeInTheDocument();
    expect(switcher).toHaveTextContent('Acme Corp');
  });

  it('clicking the switcher button opens the dropdown listing all tenants', () => {
    renderTopBar();

    const switcher = screen.getByRole('button', { name: /switch organisation/i });
    fireEvent.click(switcher);

    expect(screen.getByRole('listbox', { name: /select organisation/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /acme corp/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /beta ltd/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /gamma inc/i })).toBeInTheDocument();
  });

  it('clicking a different tenant calls switchTenant with the correct id and setActiveTenantId', async () => {
    renderTopBar();

    fireEvent.click(screen.getByRole('button', { name: /switch organisation/i }));
    expect(screen.getByRole('listbox', { name: /select organisation/i })).toBeInTheDocument();

    // Click Beta Ltd (id: 't2')
    fireEvent.click(screen.getByRole('option', { name: /beta ltd/i }));

    await waitFor(() => {
      expect(api.switchTenant).toHaveBeenCalledWith('t2');
    });
    await waitFor(() => {
      expect(authLib.setActiveTenantId).toHaveBeenCalledWith('t2');
    });
  });
});
