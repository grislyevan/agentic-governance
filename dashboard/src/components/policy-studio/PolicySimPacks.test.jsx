import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PolicySimPacks from './PolicySimPacks';

// ── API mocks ─────────────────────────────────────────────────────────────────
vi.mock('../../lib/api', () => ({
  fetchPolicies: vi.fn(),
  updatePolicy: vi.fn(),
  updateTenantPosture: vi.fn(),
}));

// ── Hook mocks ────────────────────────────────────────────────────────────────
vi.mock('../../hooks/useAuth', () => ({
  default: () => ({
    user: { id: 'u1', tenant_id: 't1', activeTenantId: 't1', role: 'admin' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────
import * as api from '../../lib/api';

const mockPolicies = {
  items: [
    { id: 'pol-1', rule_id: 'ENFORCE-001', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-2', rule_id: 'ENFORCE-002', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-3', rule_id: 'ENFORCE-003', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-4', rule_id: 'ENFORCE-004', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-5', rule_id: 'ENFORCE-D01', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-6', rule_id: 'ENFORCE-D02', is_active: true, parameters: { override_decision: 'detect' } },
    { id: 'pol-7', rule_id: 'ENFORCE-D03', is_active: true, parameters: { override_decision: 'detect' } },
  ],
};

function setupMocks() {
  api.fetchPolicies.mockResolvedValue(mockPolicies);
  api.updateTenantPosture.mockResolvedValue({});
  api.updatePolicy.mockResolvedValue({});
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('PolicySimPacks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('renders all three profile cards', () => {
    render(<PolicySimPacks onApplied={vi.fn()} />);
    expect(screen.getByText('Visibility Only')).toBeInTheDocument();
    expect(screen.getByText('Warn Heavy')).toBeInTheDocument();
    expect(screen.getByText('Approval Required — High Risk')).toBeInTheDocument();
  });

  it('each card has a Preview button', () => {
    render(<PolicySimPacks onApplied={vi.fn()} />);
    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    expect(previewButtons).toHaveLength(3);
  });

  it('clicking Preview on visibility-only shows a confirm dialog (not PreviewModal)', async () => {
    render(<PolicySimPacks onApplied={vi.fn()} />);

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    // visibility-only is first card
    fireEvent.click(previewButtons[0]);

    await waitFor(() => {
      // ConfirmDialog title: "Apply Visibility Only?"
      expect(screen.getByText(/apply visibility only\?/i)).toBeInTheDocument();
    });

    // Should NOT show the 7-day baseline warning (requiresBaseline: false)
    expect(
      screen.queryByText(/must run visibility-only for at least 7 days/i)
    ).not.toBeInTheDocument();
    // Should NOT show a diff table with "Rule overrides" header
    expect(screen.queryByText(/rule overrides/i)).not.toBeInTheDocument();
  });

  it('clicking Preview on warn-heavy shows PreviewModal with diff table AND 7-day warning banner', async () => {
    render(<PolicySimPacks onApplied={vi.fn()} />);

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    // warn-heavy is second card
    fireEvent.click(previewButtons[1]);

    await waitFor(() => {
      expect(screen.getByText(/warn heavy/i)).toBeInTheDocument();
    });

    // Diff table header
    expect(screen.getByText(/rule overrides/i)).toBeInTheDocument();
    // 7-day baseline warning banner
    expect(
      screen.getByText(/must run visibility-only for at least 7 days/i)
    ).toBeInTheDocument();
  });

  it('Apply button for warn-heavy is disabled until the "I understand" checkbox is checked', async () => {
    render(<PolicySimPacks onApplied={vi.fn()} />);

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    fireEvent.click(previewButtons[1]);

    await waitFor(() => expect(screen.getByText(/rule overrides/i)).toBeInTheDocument());

    // Find the Apply button
    const applyBtn = screen.getByRole('button', { name: /apply warn heavy/i });
    expect(applyBtn).toBeDisabled();

    // Check the "I understand" checkbox
    const checkbox = screen.getByRole('checkbox', { name: /i understand/i });
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /apply warn heavy/i })
      ).not.toBeDisabled();
    });
  });

  it('clicking Apply for visibility-only calls updateTenantPosture and updatePolicy and fires onApplied', async () => {
    const onApplied = vi.fn();
    render(<PolicySimPacks onApplied={onApplied} />);

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    fireEvent.click(previewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/apply visibility only\?/i)).toBeInTheDocument();
    });

    // Click Confirm in the ConfirmDialog
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(api.updateTenantPosture).toHaveBeenCalledWith(
        expect.objectContaining({ enforcement_posture: 'passive' })
      );
    });
    // updatePolicy should have been called for each rule override
    await waitFor(() => {
      expect(api.updatePolicy).toHaveBeenCalled();
    });
    // onApplied callback fires
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalled();
    });
  });

  it('onApplied callback is called after successful apply of warn-heavy', async () => {
    const onApplied = vi.fn();
    render(<PolicySimPacks onApplied={onApplied} />);

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    fireEvent.click(previewButtons[1]);

    await waitFor(() => expect(screen.getByText(/rule overrides/i)).toBeInTheDocument());

    // Check the acknowledgement checkbox
    const checkbox = screen.getByRole('checkbox', { name: /i understand/i });
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /apply warn heavy/i })
      ).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole('button', { name: /apply warn heavy/i }));

    await waitFor(() => expect(onApplied).toHaveBeenCalled());
    expect(api.updateTenantPosture).toHaveBeenCalledWith(
      expect.objectContaining({ enforcement_posture: 'audit' })
    );
  });
});
