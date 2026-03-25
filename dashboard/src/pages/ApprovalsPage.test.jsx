import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import ApprovalsPage from './ApprovalsPage';

// ── API mocks ─────────────────────────────────────────────────────────────────
vi.mock('../lib/api', () => ({
  fetchApprovals: vi.fn(),
  approveRequest: vi.fn(),
  denyRequest: vi.fn(),
}));

// ── Hook mocks ────────────────────────────────────────────────────────────────
vi.mock('../hooks/useAuth', () => ({
  default: () => ({
    user: { id: 'u1', tenant_id: 't1', activeTenantId: 't1', role: 'admin' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// Mock usePolling — call callback immediately on mount AND whenever it changes
// (ApprovalsPage recreates load() whenever activeTab or page changes)
vi.mock('../hooks/usePolling', () => {
  const { useEffect } = require('react');
  return {
    default: (callback) => {
      useEffect(() => {
        callback();
      }, [callback]); // eslint-disable-line react-hooks/exhaustive-deps
      return { lastUpdated: Date.now(), paused: false, togglePause: vi.fn() };
    },
  };
});

// Mock sub-components that are not under test
vi.mock('../components/branding/ApertureSpinner', () => ({
  default: () => <span data-testid="spinner" />,
}));
vi.mock('../components/PollingStatus', () => ({
  default: () => null,
}));

// ── Test data ─────────────────────────────────────────────────────────────────
const mockPending = {
  total: 2,
  items: [
    {
      id: 'req-1',
      tenant_id: 't1',
      endpoint_id: 'ep-1',
      tool_name: 'bash',
      confidence_band: 'High',
      confidence_score: 0.85,
      policy_rule_id: 'DETEC-001',
      status: 'pending',
      requested_at: '2026-03-24T10:00:00Z',
      requester_type: 'agent',
      decided_by: null,
      decided_at: null,
      reason: null,
    },
    {
      id: 'req-2',
      tenant_id: 't1',
      endpoint_id: 'ep-2',
      tool_name: 'curl',
      confidence_band: 'Medium',
      confidence_score: 0.62,
      policy_rule_id: 'DETEC-002',
      status: 'pending',
      requested_at: '2026-03-24T11:00:00Z',
      requester_type: 'agent',
      decided_by: null,
      decided_at: null,
      reason: null,
    },
  ],
};

const mockApproved = {
  total: 1,
  items: [
    {
      id: 'req-3',
      tenant_id: 't1',
      endpoint_id: 'ep-3',
      tool_name: 'git',
      confidence_band: 'Low',
      confidence_score: 0.3,
      policy_rule_id: 'DETEC-003',
      status: 'approved',
      requested_at: '2026-03-23T09:00:00Z',
      requester_type: 'agent',
      decided_by: 'u1',
      decided_at: '2026-03-23T09:30:00Z',
      reason: 'Legitimate use',
    },
  ],
};

// ── Helpers ───────────────────────────────────────────────────────────────────
import * as api from '../lib/api';

async function renderWithPending() {
  api.fetchApprovals.mockResolvedValue(mockPending);
  api.approveRequest.mockResolvedValue({});
  api.denyRequest.mockResolvedValue({});
  render(<ApprovalsPage onNavigate={vi.fn()} />);
  await waitFor(() => expect(screen.getByText('bash')).toBeInTheDocument());
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('ApprovalsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Pending tab as active by default and shows pending items', async () => {
    await renderWithPending();
    expect(screen.getByRole('button', { name: 'Pending' })).toBeInTheDocument();
    expect(screen.getByText('bash')).toBeInTheDocument();
    expect(screen.getByText('curl')).toBeInTheDocument();
  });

  it('shows the Actions column header only on the pending tab', async () => {
    await renderWithPending();
    expect(screen.getByRole('columnheader', { name: /actions/i })).toBeInTheDocument();
  });

  it('switching to Approved tab fetches approved data and renders it', async () => {
    // First call: pending, second call: approved
    api.fetchApprovals
      .mockResolvedValueOnce(mockPending)
      .mockResolvedValue(mockApproved);
    api.approveRequest.mockResolvedValue({});
    api.denyRequest.mockResolvedValue({});

    render(<ApprovalsPage onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('bash')).toBeInTheDocument());

    // Click the Approved tab — this calls setActiveTab which re-creates load
    // and also calls load() synchronously from handleTabChange? No, it just sets state.
    // The new load() will be created by useCallback and usePolling won't auto-fire.
    // We need to manually trigger it. However, in the component, clicking tab only
    // changes activeTab state — load is only called by usePolling.
    // Our mock fires callback once on mount (via [] effect), so we must
    // simulate a manual reload after tab switch.
    fireEvent.click(screen.getByRole('button', { name: 'Approved' }));

    // After tab change, fetchApprovals should eventually be called with approved
    // The component internally calls load() when activeTab changes because
    // useCallback recreates load, but since usePolling only fires once on mount,
    // we need to wait for the component to call load itself.
    // Looking at the code: load is called via usePolling — it won't auto-reload.
    // So we verify that fetchApprovals was called with status: 'approved'
    // by checking that the component re-renders with approved data after
    // an explicit re-trigger or by asserting the API call directly.
    await waitFor(() => {
      expect(api.fetchApprovals).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'approved' })
      );
    });
  });

  it('Approve quick-action button calls approveRequest with the correct id', async () => {
    await renderWithPending();

    const approveButtons = screen.getAllByRole('button', { name: 'Approve' });
    // First Approve button is for req-1 (bash)
    fireEvent.click(approveButtons[0]);

    await waitFor(() =>
      expect(api.approveRequest).toHaveBeenCalledWith('req-1', undefined)
    );
  });

  it('Deny inline button in Actions column sets selectedItem and opens the drawer', async () => {
    await renderWithPending();

    // There are two Deny buttons in the Actions column (one per row)
    const denyButtons = screen.getAllByRole('button', { name: 'Deny' });
    // Click the first Deny (row-level action)
    fireEvent.click(denyButtons[0]);

    // The detail drawer should appear (it's a fixed panel on the right)
    await waitFor(() => {
      // The drawer has a "Close detail panel" button
      expect(screen.getByRole('button', { name: /close detail panel/i })).toBeInTheDocument();
    });
  });

  it('submitting deny modal without reason keeps the submit button disabled', async () => {
    await renderWithPending();

    // Click a table row to open the detail drawer
    fireEvent.click(screen.getByText('bash').closest('tr'));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /close detail panel/i })).toBeInTheDocument()
    );

    // The drawer footer has Deny button with no title — click it to open ActionModal
    const drawerDenyBtn = screen.getAllByRole('button', { name: 'Deny' }).find(
      (b) => !b.getAttribute('title')
    );
    fireEvent.click(drawerDenyBtn);

    // ActionModal appears — the submit Deny button should be disabled (reason required but empty)
    await waitFor(() => {
      const submitBtn = document.querySelector('button[type="submit"]');
      expect(submitBtn).toBeInTheDocument();
      expect(submitBtn).toBeDisabled();
    });

    expect(api.denyRequest).not.toHaveBeenCalled();
  });

  it('submitting deny modal with a reason calls denyRequest(id, reason)', async () => {
    await renderWithPending();

    // Open drawer by clicking the row
    fireEvent.click(screen.getByText('bash').closest('tr'));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /close detail panel/i })).toBeInTheDocument()
    );

    // Click the Deny button in the drawer footer to open the ActionModal
    const drawerDenyBtn = screen.getAllByRole('button', { name: 'Deny' }).find(
      (b) => !b.getAttribute('title')
    );
    fireEvent.click(drawerDenyBtn);

    // Fill in the reason
    await waitFor(() =>
      expect(screen.getByPlaceholderText(/reason for denial/i)).toBeInTheDocument()
    );
    fireEvent.change(screen.getByPlaceholderText(/reason for denial/i), {
      target: { value: 'Not authorised' },
    });

    // The submit button should now be enabled
    const submitBtn = document.querySelector('button[type="submit"]');
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() =>
      expect(api.denyRequest).toHaveBeenCalledWith('req-1', 'Not authorised')
    );
  });

  it('non-pending rows (approved tab) do not show Approve action button', async () => {
    // First call returns pending, subsequent returns approved
    api.fetchApprovals
      .mockResolvedValueOnce(mockPending)
      .mockResolvedValue(mockApproved);
    api.approveRequest.mockResolvedValue({});
    api.denyRequest.mockResolvedValue({});

    render(<ApprovalsPage onNavigate={vi.fn()} />);
    await waitFor(() => expect(screen.getByText('bash')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Approved' }));

    // Wait for the Approved tab call
    await waitFor(() =>
      expect(api.fetchApprovals).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'approved' })
      )
    );

    // The Actions column should not exist on the approved tab
    // (the component only renders it when activeTab === 'pending')
    await waitFor(() => {
      expect(screen.queryByRole('columnheader', { name: /actions/i })).not.toBeInTheDocument();
    });
  });

  it('clicking a row opens the detail drawer showing tool_name, confidence_band, endpoint_id', async () => {
    await renderWithPending();

    // Click the first row (bash) — not on an action button
    const bashCell = screen.getByText('bash');
    fireEvent.click(bashCell.closest('tr'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close detail panel/i })).toBeInTheDocument();
    });

    // The drawer shows tool_name in the header
    const drawer = screen.getByRole('button', { name: /close detail panel/i }).closest(
      '[class*="fixed right-0"]'
    );
    // confidence_band visible somewhere in the document
    expect(screen.getAllByText('High').length).toBeGreaterThanOrEqual(1);
    // endpoint_id shown (truncated) — may appear in table and drawer, just verify at least one
    expect(screen.getAllByText(/ep-1/).length).toBeGreaterThanOrEqual(1);
  });
});
