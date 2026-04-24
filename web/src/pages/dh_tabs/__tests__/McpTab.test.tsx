/**
 * McpTab tests — empty pool shows the hint.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import McpTab from '../McpTab';
import * as api from '../../../utils/api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe('McpTab', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: vi.fn(() => 'fake'), setItem: vi.fn(), removeItem: vi.fn() },
      writable: true,
    });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders empty-pool hint when pool is {}', async () => {
    vi.spyOn(api, 'apiFetch').mockResolvedValueOnce({ pool: {}, enabled: [] });
    render(<McpTab dhId="executor" />);
    await waitFor(() =>
      expect(screen.getByText('dh.tab.mcp.poolEmpty')).toBeInTheDocument(),
    );
  });
});
