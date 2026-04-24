/**
 * First frontend test — DHFilter component.
 * Runs under vitest + jsdom. See vitest.config.ts.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DHFilter from '../DHFilter';
import * as api from '../../utils/api';

describe('DHFilter', () => {
  beforeEach(() => {
    // Mock localStorage for apiFetch auth
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(() => 'fake-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders nothing when no DHs configured', async () => {
    vi.spyOn(api, 'apiFetch').mockResolvedValueOnce([]);
    const onChange = vi.fn();
    const { container } = render(<DHFilter value={null} onChange={onChange} />);
    // Wait briefly for the async fetch to resolve
    await waitFor(() => expect(api.apiFetch).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });

  it('renders All + one button per DH', async () => {
    vi.spyOn(api, 'apiFetch').mockResolvedValueOnce([
      { id: 'executor', config: { enabled: true } },
      { id: 'observer', config: { enabled: true } },
    ]);
    render(<DHFilter value={null} onChange={vi.fn()} />);
    expect(await screen.findByText('全部')).toBeInTheDocument();
    expect(screen.getByText('Executor')).toBeInTheDocument();
    expect(screen.getByText('Observer')).toBeInTheDocument();
  });

  it('invokes onChange(null) when "全部" clicked', async () => {
    vi.spyOn(api, 'apiFetch').mockResolvedValueOnce([
      { id: 'executor', config: { enabled: true } },
    ]);
    const onChange = vi.fn();
    render(<DHFilter value="executor" onChange={onChange} />);
    await screen.findByText('全部');
    fireEvent.click(screen.getByText('全部'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('invokes onChange(id) when DH button clicked', async () => {
    vi.spyOn(api, 'apiFetch').mockResolvedValueOnce([
      { id: 'observer', config: { enabled: true } },
    ]);
    const onChange = vi.fn();
    render(<DHFilter value={null} onChange={onChange} />);
    await screen.findByText('Observer');
    fireEvent.click(screen.getByText('Observer'));
    expect(onChange).toHaveBeenCalledWith('observer');
  });

  it('apiFetch error → component renders nothing (silent degradation)', async () => {
    vi.spyOn(api, 'apiFetch').mockRejectedValueOnce(new Error('network'));
    const { container } = render(<DHFilter value={null} onChange={vi.fn()} />);
    await waitFor(() => expect(api.apiFetch).toHaveBeenCalled());
    expect(container.firstChild).toBeNull();
  });
});
