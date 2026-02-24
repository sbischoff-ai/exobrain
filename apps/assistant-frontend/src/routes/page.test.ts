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

class MockEventSource {
  static latest: MockEventSource | null = null;
  readyState = 1;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, Array<(event: MessageEvent) => void>>();

  constructor(_url: string) {
    MockEventSource.latest = this;
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), handler]);
  }

  emit(type: string, data: unknown): void {
    for (const handler of this.listeners.get(type) ?? []) {
      handler({ data: JSON.stringify(data), currentTarget: this } as unknown as MessageEvent);
    }
  }

  close(): void {
    this.readyState = 2;
  }
}

describe('root page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
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


  it('renders persisted tool call info boxes from fetched journal messages', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/01/01', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 'm2',
            role: 'assistant',
            content: 'Result is ready',
            sequence: 2,
            tool_calls: [
              {
                tool_call_id: 'tc-1',
                title: 'Web search',
                description: 'Searching the web',
                response: 'Found 3 sources',
                error: null
              },
              {
                tool_call_id: 'tc-2',
                title: 'Database lookup',
                description: 'Checking records',
                response: null,
                error: 'Lookup failed'
              }
            ]
          },
          { id: 'm1', role: 'user', content: 'Find sources', sequence: 1, tool_calls: [] }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByText('Web search')).toBeInTheDocument();
      expect(screen.getByText('Found 3 sources')).toBeInTheDocument();
      expect(screen.getByText('Database lookup')).toBeInTheDocument();
      expect(screen.getByText('Lookup failed')).toBeInTheDocument();
    });

    const stored = JSON.parse(window.sessionStorage.getItem('exobrain.assistant.session') || '{}');
    expect(stored.messages[1].toolCalls).toHaveLength(2);
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




  it('streams chat chunks and tool status via EventSource', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ stream_id: 'stream-1' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByLabelText('Type your message')).not.toBeDisabled();
    });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Need research' } });
    await fireEvent.submit(input.closest('form')!);

    const source = MockEventSource.latest!;
    source.emit('tool_call', { tool_call_id: 'tc-1', title: 'Web search', description: 'Searching the web' });
    source.emit('message_chunk', { text: 'assistant reply' });
    source.emit('tool_response', { tool_call_id: 'tc-1', message: 'Found 1 source' });
    source.emit('done', { reason: 'complete' });

    await waitFor(() => {
      expect(screen.getByText('assistant reply')).toBeInTheDocument();
      expect(screen.getByText('Web search')).toBeInTheDocument();
      expect(screen.getByText('Found 1 source')).toBeInTheDocument();
    });
  });



  it('maps out-of-order tool responses to matching tool_call_id boxes', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ stream_id: 'stream-1' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByLabelText('Type your message')).not.toBeDisabled();
    });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Need research' } });
    await fireEvent.submit(input.closest('form')!);

    const source = MockEventSource.latest!;
    source.emit('tool_call', { tool_call_id: 'tc-1', title: 'Web search', description: 'Searching for alpha' });
    source.emit('tool_call', { tool_call_id: 'tc-2', title: 'Web fetch', description: 'Looking at beta' });
    source.emit('tool_response', { tool_call_id: 'tc-2', message: 'Summarized beta page' });
    source.emit('tool_response', { tool_call_id: 'tc-1', message: 'Found alpha source' });
    source.emit('done', { reason: 'complete' });

    await waitFor(() => {
      expect(screen.getByText('Found alpha source')).toBeInTheDocument();
      expect(screen.getByText('Summarized beta page')).toBeInTheDocument();
    });

    const descriptions = Array.from(document.querySelectorAll('.process-description')).map((el) => el.textContent?.trim() ?? '');
    const responses = Array.from(document.querySelectorAll('.process-response')).map((el) => el.textContent?.trim() ?? '');

    expect(descriptions).toContain('Searching for alpha');
    expect(descriptions).toContain('Looking at beta');
    expect(descriptions).not.toContain('Searching for alpha...');
    expect(descriptions).not.toContain('Looking at beta...');
    expect(responses).toContain('Found alpha source');
    expect(responses).toContain('Summarized beta page');
  });


  it('stops live stream updates when switching journals and resumes when returning to today', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );

    vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2025/01/14' }]))
      .mockResolvedValueOnce(jsonResponse({ stream_id: 'stream-1' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2025/01/14' }]))
      .mockResolvedValueOnce(jsonResponse({ reference: '2025/01/14', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse([]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByLabelText('Type your message')).not.toBeDisabled();
    });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Need research' } });
    await fireEvent.submit(input.closest('form')!);

    const source = MockEventSource.latest!;
    source.emit('message_chunk', { text: 'partial reply' });

    await waitFor(() => {
      expect(screen.getByText('partial reply')).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open journals' }));
    await fireEvent.click(screen.getByRole('button', { name: '2025/01/14' }));

    await waitFor(() => {
      expect(screen.queryByText('partial reply')).not.toBeInTheDocument();
    });

    expect(window.sessionStorage.getItem('exobrain.assistant.pendingStreamId')).toBe('stream-1');

    await fireEvent.click(screen.getByRole('button', { name: 'Open journals' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Today · 2026/02/19' }));

    await waitFor(() => {
      expect(MockEventSource.latest).not.toBe(source);
    });

    const resumedSource = MockEventSource.latest!;
    resumedSource.emit('message_chunk', { text: ' resumed reply' });
    resumedSource.emit('done', { reason: 'complete' });

    await waitFor(() => {
      expect(screen.getByText(/resumed reply/)).toBeInTheDocument();
      expect(window.sessionStorage.getItem('exobrain.assistant.pendingStreamId')).toBeNull();
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
