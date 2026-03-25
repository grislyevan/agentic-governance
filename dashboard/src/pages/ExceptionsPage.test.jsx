import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import ExceptionsPage from './ExceptionsPage';

// ── API mocks ─────────────────────────────────────────────────────────────────
vi.mock('../lib/api', () => ({
  fetchAllowList: vi.fn(),
  createAllowListEntry: vi.fn(),
  updateAllowListEntry: vi.fn(),
  deleteAllowListEntry: vi.fn(),
}));

// ── Hook mocks ────────────────────────────────────────────────────────────────
vi.mock('../hooks/useAuth', () => ({
  default: () => ({
    user: { id: 'u1', tenant_id: 't1', activeTenantId: 't1', role: 'admin' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// ── Test data ─────────────────────────────────────────────────────────────────
const mockEntries = {
  items: [
    {
      id: 'al-1',
      pattern: 'cursor',
      pattern_type: 'name',
      scope: 'tenant',
      reason_code: 'FP-CURSOR-001',
      owner_id: 'u1',
      expires_at: null,
      created_at: '2026-03-01T00:00:00Z',
      description: 'Cursor IDE baseline',
    },
    {
      id: 'al-2',
      pattern: '/usr/bin/node',
      pattern_type: 'path',
      scope: 'tenant',
      reason_code: 'FP-NODE-001',
      owner_id: 'u1',
      expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: '2026-03-10T00:00:00Z',
      description: null,
    },
    {
      id: 'al-3',
      pattern: 'ollama',
      pattern_type: 'name',
      scope: 'tenant',
      reason_code: 'FP-OLLAMA-001',
      owner_id: 'u1',
      expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: '2026-03-15T00:00:00Z',
      description: 'Ollama local model',
    },
  ],
};

// ── Helpers ───────────────────────────────────────────────────────────────────
import * as api from '../lib/api';

async function renderAndLoad() {
  api.fetchAllowList.mockResolvedValue(mockEntries);
  api.createAllowListEntry.mockResolvedValue({});
  api.deleteAllowListEntry.mockResolvedValue({});
  render(<ExceptionsPage />);
  // Wait until the table data loads
  await waitFor(() => expect(screen.getByText('cursor')).toBeInTheDocument());
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('ExceptionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the exceptions list with all three entries', async () => {
    await renderAndLoad();
    expect(screen.getByText('cursor')).toBeInTheDocument();
    expect(screen.getByText('/usr/bin/node')).toBeInTheDocument();
    expect(screen.getByText('ollama')).toBeInTheDocument();
  });

  it('"No expiry" badge renders for entries with expires_at null', async () => {
    await renderAndLoad();
    const noExpiryBadges = screen.getAllByText('No expiry');
    expect(noExpiryBadges.length).toBeGreaterThanOrEqual(1);
    // The badge for al-1 (cursor) should have red styling
    const badge = noExpiryBadges[0];
    expect(badge.className).toMatch(/red/);
  });

  it('"Expiring soon" badge renders amber for entries expiring within 7 days', async () => {
    await renderAndLoad();
    // The badge has text like "Expiring soon · in X days"
    // Filter out the filter pill button which also contains "Expiring Soon"
    const badges = screen
      .getAllByText(/expiring soon/i)
      .filter((el) => el.tagName !== 'BUTTON');
    expect(badges.length).toBeGreaterThanOrEqual(1);
    const badge = badges[0];
    expect(badge.className).toMatch(/amber/);
  });

  it('"Add Exception" button opens the create drawer', async () => {
    await renderAndLoad();
    // The page header button says "Add Exception" — use the button role
    const addBtn = screen.getByRole('button', { name: /add exception/i });
    fireEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    // The drawer heading says "Add Exception"
    expect(screen.getAllByText(/add exception/i).length).toBeGreaterThanOrEqual(1);
  });

  it('submitting create form WITHOUT reason_code does not call createAllowListEntry', async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole('button', { name: /add exception/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    // Fill pattern but leave reason_code blank
    fireEvent.change(screen.getByPlaceholderText(/cursor-agent/i), {
      target: { value: 'my-tool' },
    });
    // Fill expires_at so only reason_code is missing
    const datetimeInput = document.querySelector('input[type="datetime-local"]');
    fireEvent.change(datetimeInput, { target: { value: '2026-12-01T00:00' } });

    // Submit via fireEvent.submit to bypass native HTML5 required-field validation
    // and trigger the component's own JS validate() function
    fireEvent.submit(document.querySelector('form'));

    await waitFor(() => {
      expect(screen.getByText(/reason code is required/i)).toBeInTheDocument();
    });
    expect(api.createAllowListEntry).not.toHaveBeenCalled();
  });

  it('submitting WITHOUT expires_at (and without override) does not call createAllowListEntry', async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole('button', { name: /add exception/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    // Fill pattern and reason_code but leave expires_at blank
    fireEvent.change(screen.getByPlaceholderText(/cursor-agent/i), {
      target: { value: 'my-tool' },
    });
    fireEvent.change(screen.getByPlaceholderText(/FP-CURSOR-001/i), {
      target: { value: 'FP-TEST-001' },
    });
    // Do NOT fill expires_at, do NOT check override
    // Use fireEvent.submit to bypass native HTML5 required-field validation
    fireEvent.submit(document.querySelector('form'));

    // The validation error text is: "Expiry date is required unless override is checked."
    await waitFor(() => {
      const errorDiv = document.querySelector('form [class*="red"]');
      expect(errorDiv).toBeTruthy();
      expect(errorDiv.textContent).toMatch(/expiry date is required/i);
    });
    expect(api.createAllowListEntry).not.toHaveBeenCalled();
  });

  it('checking the no-expiry override checkbox shows warning banner', async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole('button', { name: /add exception/i }));

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    const dialog = screen.getByRole('dialog');
    const overrideCheckbox = within(dialog).getByRole('checkbox');
    fireEvent.click(overrideCheckbox);

    await waitFor(() => {
      expect(
        screen.getByText(/non-expiring exceptions require review/i)
      ).toBeInTheDocument();
    });
  });

  it('submitting a valid form with reason_code + expires_at calls createAllowListEntry', async () => {
    await renderAndLoad();
    fireEvent.click(screen.getByRole('button', { name: /add exception/i }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument());

    // Fill all required fields
    fireEvent.change(screen.getByPlaceholderText(/cursor-agent/i), {
      target: { value: 'my-tool' },
    });
    fireEvent.change(screen.getByPlaceholderText(/FP-CURSOR-001/i), {
      target: { value: 'FP-MY-001' },
    });
    const datetimeInput = document.querySelector('input[type="datetime-local"]');
    fireEvent.change(datetimeInput, { target: { value: '2026-12-01T00:00' } });

    // Submit the form
    fireEvent.submit(document.querySelector('form'));

    await waitFor(() =>
      expect(api.createAllowListEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          pattern: 'my-tool',
          reason_code: 'FP-MY-001',
        })
      )
    );
  });

  it('Delete button triggers inline confirm dialog; confirming calls deleteAllowListEntry(id)', async () => {
    await renderAndLoad();

    // Find the delete (trash) button for the first row (cursor / al-1)
    const trashButtons = screen.getAllByTitle('Delete');
    fireEvent.click(trashButtons[0]);

    // Confirm dialog appears inline
    await waitFor(() => {
      expect(screen.getByText(/delete this exception\?/i)).toBeInTheDocument();
    });

    // Click "Confirm delete"
    fireEvent.click(screen.getByRole('button', { name: /confirm delete/i }));

    await waitFor(() =>
      expect(api.deleteAllowListEntry).toHaveBeenCalledWith('al-1')
    );
  });
});
