import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';
import * as auth from '../lib/auth';

vi.mock('../lib/auth', () => ({
  STORAGE_KEYS: { apiUrl: 'detec_api_url', apiKey: 'detec_api_key', activeTenantId: 'detec_active_tenant_id' },
  getStoredTokens: () => ({ accessToken: '', refreshToken: '' }),
  getActiveTenantId: () => null,
  storeTokens: () => {},
  clearTokens: () => Promise.resolve(),
  fetchCurrentUser: () => Promise.resolve(null),
  getUserRole: vi.fn().mockReturnValue('viewer'),
  setUserRole: vi.fn(),
}));

// Mock the hooks that make API calls
vi.mock('../hooks/useEndpoints', () => ({
  default: vi.fn(() => ({
    tools: [],
    counts: { block: 0, approval_required: 0, warn: 0, detect: 0 },
    endpointCount: 0,
    endpoints: [],
    endpointStatuses: [],
    profiles: [],
    loading: false,
    error: null,
    refresh: vi.fn(),
    filters: { observedAfter: null, endpointId: null },
    updateFilters: vi.fn(),
  })),
}));

vi.mock('../hooks/usePolling', () => ({
  default: vi.fn(() => ({
    lastUpdated: null,
    paused: false,
    togglePause: vi.fn(),
  })),
}));

// Mock all api functions used by DashboardPage
vi.mock('../lib/api', () => ({
  fetchEvents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getApiConfig: vi.fn().mockReturnValue({ apiUrl: 'http://localhost:8000/api', apiKey: '' }),
}));

// Stub widgets that have complex internal logic
vi.mock('../components/dashboard/PostureSummaryWidget', () => ({
  default: function MockPostureSummaryWidget() { return <div>PostureSummaryWidget</div>; },
}));
vi.mock('../components/dashboard/CapabilityDriftWidget', () => ({
  default: function MockCapabilityDriftWidget() { return <div>CapabilityDriftWidget</div>; },
}));
vi.mock('../components/dashboard/DataFlowWidget', () => ({
  default: function MockDataFlowWidget() { return <div>DataFlowWidget</div>; },
}));
vi.mock('../components/dashboard/ResponseTimelineWidget', () => ({
  default: function MockResponseTimelineWidget() { return <div>ResponseTimelineWidget</div>; },
}));
vi.mock('../components/dashboard/SystemStatusBanner', () => ({
  default: function MockSystemStatusBanner() { return <div>SystemStatusBanner</div>; },
}));
vi.mock('../components/dashboard/EndpointContextBar', () => ({
  default: function MockEndpointContextBar() { return <div>EndpointContextBar</div>; },
}));

describe('DashboardPage role gating', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows admin-only panels for owner', async () => {
    auth.getUserRole.mockReturnValue('owner');
    render(<MemoryRouter><DashboardPage onAlertCountChange={() => {}} /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByTestId('posture-summary-widget')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('shows admin-only panels for admin', async () => {
    auth.getUserRole.mockReturnValue('admin');
    render(<MemoryRouter><DashboardPage onAlertCountChange={() => {}} /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByTestId('posture-summary-widget')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('hides admin-only panels for viewer', async () => {
    auth.getUserRole.mockReturnValue('viewer');
    render(<MemoryRouter><DashboardPage onAlertCountChange={() => {}} /></MemoryRouter>);
    await new Promise(r => setTimeout(r, 100));
    expect(screen.queryByTestId('posture-summary-widget')).not.toBeInTheDocument();
  });

  it('hides admin-only panels for analyst', async () => {
    auth.getUserRole.mockReturnValue('analyst');
    render(<MemoryRouter><DashboardPage onAlertCountChange={() => {}} /></MemoryRouter>);
    await new Promise(r => setTimeout(r, 100));
    expect(screen.queryByTestId('posture-summary-widget')).not.toBeInTheDocument();
  });
});
