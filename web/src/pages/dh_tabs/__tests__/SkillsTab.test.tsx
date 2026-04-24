/**
 * SkillsTab tests — renders checkboxes, save triggers PUT with payload.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SkillsTab from '../SkillsTab';
import * as api from '../../../utils/api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe('SkillsTab', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: vi.fn(() => 'fake'), setItem: vi.fn(), removeItem: vi.fn() },
      writable: true,
    });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders skill checkboxes and PUTs on save', async () => {
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce({
        all: ['coding', 'research', 'browsing'],
        whitelisted: ['coding'],
      })
      .mockResolvedValueOnce({ status: 'ok' });

    render(<SkillsTab dhId="executor" />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));

    // All 3 slugs rendered
    expect(screen.getByText('coding')).toBeInTheDocument();
    expect(screen.getByText('research')).toBeInTheDocument();
    expect(screen.getByText('browsing')).toBeInTheDocument();

    // coding initially checked
    const codingBox = screen.getByLabelText('coding') as HTMLInputElement;
    expect(codingBox.checked).toBe(true);

    const researchBox = screen.getByLabelText('research') as HTMLInputElement;
    expect(researchBox.checked).toBe(false);
    fireEvent.click(researchBox);
    expect(researchBox.checked).toBe(true);

    fireEvent.click(screen.getByText('common.save'));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    const putCall = spy.mock.calls.find((c) => (c[1] as { method?: string })?.method === 'PUT');
    expect(putCall).toBeDefined();
    expect(putCall![0]).toBe('/api/digital_humans/executor/skills');
    const body = JSON.parse((putCall![1] as { body: string }).body);
    expect(new Set(body.whitelisted)).toEqual(new Set(['coding', 'research']));
  });
});
