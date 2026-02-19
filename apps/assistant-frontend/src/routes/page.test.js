import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Page from './+page.svelte';

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload
  };
}

describe('root page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it('shows intro login page when no active session exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({}, 401));

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
    });
  });

  it('hydrates from session storage and shows journal reference after login check', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/01/01',
        messageCount: 1,
        messages: [{ role: 'assistant', content: 'cached' }]
      })
    );

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/01/01', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { role: 'assistant', content: 'server hello' },
          { role: 'user', content: 'server hi' }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]));

    globalThis.fetch.mockResolvedValue(jsonResponse({}, 401));

    render(Page);

    await waitFor(() => {
      expect(screen.getByText('Journal:')).toBeInTheDocument();
      expect(screen.getByText('2026/01/01')).toBeInTheDocument();
      expect(screen.getByText('server hello')).toBeInTheDocument();
    });
  });
});
