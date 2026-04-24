/**
 * IdentityPrompts page tests.
 * Covers DH tab switch, file tab switch, dirty state, save flow.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render as rtlRender, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IdentityPrompts from '../IdentityPrompts';
import * as api from '../../utils/api';

const render = (ui: React.ReactElement) =>
  rtlRender(<MemoryRouter>{ui}</MemoryRouter>);

// Minimal i18next mock so useTranslation doesn't need a real provider
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe('IdentityPrompts', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(() => 'fake'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads DHs then shows tabs + persona content', async () => {
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce([
        { id: 'executor', config: { enabled: true } },
        { id: 'observer', config: { enabled: true } },
      ])
      .mockResolvedValueOnce({
        digital_human_id: 'executor',
        files: {
          'identity.md': '# Executor identity',
          'knowledge.md': '',
          'principles.md': null,
        },
      });
    render(<IdentityPrompts />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    // Both DH tabs visible
    expect(screen.getByText('executor')).toBeInTheDocument();
    expect(screen.getByText('observer')).toBeInTheDocument();
    // File tabs
    expect(screen.getByText('identity.md')).toBeInTheDocument();
    expect(screen.getByText('knowledge.md')).toBeInTheDocument();
    expect(screen.getByText('principles.md')).toBeInTheDocument();
    // Editor shows the active file content
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toContain('Executor identity'));
  });

  it('switches DH + refetches persona', async () => {
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce([
        { id: 'executor', config: { enabled: true } },
        { id: 'observer', config: { enabled: true } },
      ])
      .mockResolvedValueOnce({
        digital_human_id: 'executor',
        files: { 'identity.md': 'exec', 'knowledge.md': null, 'principles.md': null },
      })
      .mockResolvedValueOnce({
        digital_human_id: 'observer',
        files: { 'identity.md': 'obs', 'knowledge.md': null, 'principles.md': null },
      });
    render(<IdentityPrompts />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByText('observer'));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(3));
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe('obs'));
  });

  it('switches file tab + swaps draft content', async () => {
    vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce([{ id: 'executor', config: { enabled: true } }])
      .mockResolvedValueOnce({
        digital_human_id: 'executor',
        files: {
          'identity.md': 'IDENTITY',
          'knowledge.md': 'KNOWLEDGE',
          'principles.md': 'PRINCIPLES',
        },
      });
    render(<IdentityPrompts />);
    const textarea = await screen.findByRole('textbox') as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe('IDENTITY'));
    fireEvent.click(screen.getByText('knowledge.md'));
    await waitFor(() => expect(textarea.value).toBe('KNOWLEDGE'));
    fireEvent.click(screen.getByText('principles.md'));
    await waitFor(() => expect(textarea.value).toBe('PRINCIPLES'));
  });

  it('save button triggers PUT with correct payload', async () => {
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce([{ id: 'executor', config: { enabled: true } }])
      .mockResolvedValueOnce({
        digital_human_id: 'executor',
        files: { 'identity.md': 'old', 'knowledge.md': null, 'principles.md': null },
      })
      .mockResolvedValueOnce({ status: 'ok' })
      // reload after save
      .mockResolvedValueOnce({
        digital_human_id: 'executor',
        files: { 'identity.md': 'new content', 'knowledge.md': null, 'principles.md': null },
      });
    render(<IdentityPrompts />);
    const textarea = await screen.findByRole('textbox') as HTMLTextAreaElement;
    await waitFor(() => expect(textarea.value).toBe('old'));
    fireEvent.change(textarea, { target: { value: 'new content' } });
    fireEvent.click(screen.getByText('common.save'));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(4));
    const putCall = spy.mock.calls.find(
      (c) => (c[1] as any)?.method === 'PUT'
    );
    expect(putCall).toBeDefined();
    expect(putCall![0]).toBe('/api/digital_humans/executor/persona/identity.md');
    expect(JSON.parse((putCall![1] as any).body)).toEqual({ content: 'new content' });
  });
});
