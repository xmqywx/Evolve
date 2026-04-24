/**
 * DigitalHumanDetail page tests — tabbed shell, URL param, tab switching.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DigitalHumanDetail from '../DigitalHumanDetail';
import * as api from '../../utils/api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe('DigitalHumanDetail', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: vi.fn(() => 'fake'), setItem: vi.fn(), removeItem: vi.fn() },
      writable: true,
    });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  const renderAt = (path: string) =>
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/digital_humans/:id" element={<DigitalHumanDetail />} />
        </Routes>
      </MemoryRouter>,
    );

  it('renders tab buttons after load + switches active tab on click', async () => {
    const dhDetail = {
      id: 'executor',
      config: {
        persona_dir: 'persona/executor',
        cmux_session: 'executor',
        provider: 'codex',
        heartbeat_interval_secs: 1800,
        skill_whitelist: ['*'],
        endpoint_allowlist: ['heartbeat'],
        enabled: true,
      },
      state: {
        cmux_session: 'executor',
        started_at: null,
        last_heartbeat_at: null,
        restart_count: 0,
        last_crash: null,
        enabled: true,
      },
    };
    const persona = {
      digital_human_id: 'executor',
      files: { 'identity.md': 'hi', 'knowledge.md': null, 'principles.md': null },
    };
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce(dhDetail)   // GET /api/digital_humans/executor
      .mockResolvedValueOnce(persona);   // GET persona if identity clicked

    renderAt('/digital_humans/executor');

    await waitFor(() => expect(spy).toHaveBeenCalled());

    // All 7 tab labels render
    expect(await screen.findByText('dh.tabs.overview')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.identity')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.prompt')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.skills')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.mcp')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.model')).toBeInTheDocument();
    expect(screen.getByText('dh.tabs.capabilities')).toBeInTheDocument();

    // Overview by default — persona_dir rendered
    expect(screen.getByText(/persona\/executor/)).toBeInTheDocument();

    // Click Identity tab → triggers persona fetch
    fireEvent.click(screen.getByText('dh.tabs.identity'));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        '/api/digital_humans/executor/persona',
      ),
    );
  });

  it('shows not-found when backend returns error', async () => {
    vi.spyOn(api, 'apiFetch').mockRejectedValueOnce(new Error('API error: 404'));
    renderAt('/digital_humans/ghost');
    expect(await screen.findByText(/Digital Human not found/)).toBeInTheDocument();
    expect(screen.getByText('dh.back')).toBeInTheDocument();
  });
});
