/**
 * ModelTab tests — dropdown change triggers PUT.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ModelTab from '../ModelTab';
import * as api from '../../../utils/api';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

describe('ModelTab', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: vi.fn(() => 'fake'), setItem: vi.fn(), removeItem: vi.fn() },
      writable: true,
    });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('changes dropdown → sends PUT with {model}', async () => {
    const spy = vi.spyOn(api, 'apiFetch')
      .mockResolvedValueOnce({
        current: '',
        provider: 'codex',
        global_default: 'gpt-5.5',
      })
      .mockResolvedValueOnce({ status: 'ok' });

    render(<ModelTab dhId="observer" />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));

    const select = screen.getByLabelText('model') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'gpt-5.5-mini' } });

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    const putCall = spy.mock.calls.find((c) => (c[1] as { method?: string })?.method === 'PUT');
    expect(putCall).toBeDefined();
    expect(putCall![0]).toBe('/api/digital_humans/observer/model');
    expect(JSON.parse((putCall![1] as { body: string }).body)).toEqual({
      model: 'gpt-5.5-mini',
    });
  });
});
