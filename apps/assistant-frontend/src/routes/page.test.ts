import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Page from './+page.svelte';

function jsonResponse<T>(payload: T, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload
  } as Response;
}



function streamResponse(chunks: string[], status = 200, delayMs = 0): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) {
        if (delayMs > 0) {
          await new Promise((resolve) => setTimeout(resolve, delayMs));
        }
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    }
  });

  return {
    ok: status >= 200 && status < 300,
    status,
    body
  } as Response;
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

  it('hydrates from session storage and fetches only the latest 50 messages when counts differ', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/01/01',
        messageCount: 1,
        messages: [{ role: 'assistant', content: 'cached', clientMessageId: 'existing-id', sequence: 1 }]
      })
    );

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/01/01', message_count: 70 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'server hello', sequence: 70 },
          { id: 'm2', role: 'user', content: 'server hi', sequence: 69 }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByText('Journal:')).toBeInTheDocument();
      expect(screen.getByText('server hello')).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalledWith('/api/journal/2026/01/01/messages?limit=50', undefined);
    expect(screen.getByRole('button', { name: 'Load older messages' })).toBeInTheDocument();
  });

  it('loads older messages using cursor pagination and prepends them chronologically', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/01/01',
        messageCount: 55,
        messages: [
          { role: 'assistant', content: 'newer', clientMessageId: 'existing-id-2', sequence: 55 },
          { role: 'assistant', content: 'newest', clientMessageId: 'existing-id-3', sequence: 56 }
        ]
      })
    );

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/01/01', message_count: 55 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'older a', sequence: 53 },
          { id: 'm2', role: 'assistant', content: 'older b', sequence: 54 }
        ])
      );

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Load older messages' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Load older messages' }));

    await waitFor(() => {
      expect(screen.getByText('older a')).toBeInTheDocument();
      expect(screen.getByText('older b')).toBeInTheDocument();
      expect(screen.getByText('newer')).toBeInTheDocument();
      expect(screen.getByText('newest')).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalledWith('/api/journal/2026/01/01/messages?limit=50&cursor=55', undefined);
  });


  it('disables chat with tooltip for past journals selected from sidebar', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2025/01/14' }]))
      .mockResolvedValueOnce(jsonResponse({ reference: '2025/01/14', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'older context', sequence: 2 },
          { id: 'm2', role: 'user', content: 'question', sequence: 1 }
        ])
      );

    render(Page);

    await waitFor(() => {
      expect(screen.getByLabelText('Type your message')).not.toBeDisabled();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open journals' }));
    await fireEvent.click(screen.getByRole('button', { name: '2025/01/14' }));

    await waitFor(() => {
      const input = screen.getByLabelText('Type your message');
      const send = screen.getByRole('button', { name: 'Send message' });
      expect(input).toBeDisabled();
      expect(send).toBeDisabled();
      expect(input).toHaveAttribute('title', 'You can not chat with past journals.');
      expect(send).toHaveAttribute('title', 'You can not chat with past journals.');
    });
  });


  it('collapses the journal sidebar when clicking outside it', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2025/01/14' }]));

    const { container } = render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Open journals' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open journals' }));

    const overlay = container.querySelector('.journal-overlay') as HTMLElement;

    await waitFor(() => {
      expect(overlay).toHaveClass('open');
    });

    await fireEvent.mouseDown(document.body);

    await waitFor(() => {
      expect(overlay).not.toHaveClass('open');
    });
  });



  it('shows Thinking placeholder until the first stream chunk arrives', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(streamResponse(['assistant reply'], 200, 50))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByLabelText('Type your message')).not.toBeDisabled();
    });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Need research' } });
    await fireEvent.submit(input.closest('form')!);

    expect(screen.getByText('Thinking ...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('Thinking ...')).not.toBeInTheDocument();
      expect(screen.getByText('assistant reply')).toBeInTheDocument();
    });
  });

  it('clears session storage and returns to intro page after logout', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/01/01',
        messageCount: 0,
        messages: []
      })
    );

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/01/01', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]))
      .mockResolvedValueOnce({ ok: true, status: 204 } as Response);

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Open user menu' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
      expect(window.sessionStorage.getItem('exobrain.assistant.session')).toBeNull();
    });
  });
});
