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
  static instances: MockEventSource[] = [];
  url: string;
  readyState = 1;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn(() => {
    this.readyState = 2;
  });
  private listeners = new Map<string, Array<(event: MessageEvent) => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.latest = this;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), handler]);
  }

  emit(type: string, data: unknown): void {
    for (const handler of this.listeners.get(type) ?? []) {
      handler({ data: JSON.stringify(data), currentTarget: this } as unknown as MessageEvent);
    }
  }

}

describe('root page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
    window.localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    MockEventSource.latest = null;
    MockEventSource.instances = [];
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
      const knowledgeUpdate = screen.getByRole('button', { name: 'Update knowledge base' });
      expect(input).toBeDisabled();
      expect(send).toBeDisabled();
      expect(knowledgeUpdate).toBeDisabled();
      expect(knowledgeUpdate).toHaveAttribute('title', 'Switch to today to update knowledge base');
      expect(input).toHaveAttribute('title', 'You can not chat with past journals.');
      expect(send).toHaveAttribute('title', 'You can not chat with past journals.');
    });
  });


  it('applies and previews theme from frontend.theme config', async () => {
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
      .mockResolvedValueOnce(
        jsonResponse({
          configs: [
            {
              key: 'frontend.theme',
              name: 'Theme',
              config_type: 'choice',
              description: 'Select theme',
              options: [
                { value: 'gruvbox-dark', label: 'Gruvbox Dark' },
                { value: 'purple-intelligence', label: 'Purple Intelligence' }
              ],
              value: 'purple-intelligence',
              default_value: 'gruvbox-dark',
              using_default: false
            }
          ]
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          configs: [
            {
              key: 'frontend.theme',
              name: 'Theme',
              config_type: 'choice',
              description: 'Select theme',
              options: [
                { value: 'gruvbox-dark', label: 'Gruvbox Dark' },
                { value: 'purple-intelligence', label: 'Purple Intelligence' }
              ],
              value: 'purple-intelligence',
              default_value: 'gruvbox-dark',
              using_default: false
            }
          ]
        })
      );

    render(Page);

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('purple-intelligence');
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    const themeSelect = await screen.findByLabelText('Theme');

    await fireEvent.change(themeSelect, { target: { value: 'gruvbox-dark' } });
    expect(document.documentElement.getAttribute('data-theme')).toBe('gruvbox-dark');

    await fireEvent.keyDown(window, { key: 'Escape' });

    await waitFor(() => {
      expect(document.documentElement.getAttribute('data-theme')).toBe('purple-intelligence');
    });
  });


  it('toggles header view mode button and persists workspace mode', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          categories: [{ category_id: 'cat-1', display_name: 'Category 1', page_count: 1, sub_categories: [] }]
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({ knowledge_pages: [{ id: 'page-1', title: 'Page 1', summary: 'summary' }] })
      );

    render(Page);

    const toggleToKnowledgeButton = await screen.findByRole('button', {
      name: 'Switch to Knowledge Explorer'
    });
    expect(toggleToKnowledgeButton).toHaveAttribute('title', 'Switch to Knowledge Explorer');

    await fireEvent.click(toggleToKnowledgeButton);

    const persistedKnowledge = JSON.parse(window.sessionStorage.getItem('exobrain.assistant.workspaceView') || '{}');
    expect(persistedKnowledge.mode).toBe('knowledge');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Switch to Journal Chat' })).toBeInTheDocument();
      expect(screen.getByLabelText('Knowledge explorer')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Open journals' })).not.toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Switch to Journal Chat' }));

    const persistedChat = JSON.parse(window.sessionStorage.getItem('exobrain.assistant.workspaceView') || '{}');
    expect(persistedChat.mode).toBe('chat');
  });


  it('restores last selected journal from session storage in chat mode', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2025/01/14',
        messageCount: 1,
        messages: [{ role: 'assistant', content: 'cached', clientMessageId: 'cached-1', sequence: 1 }]
      })
    );
    window.sessionStorage.setItem(
      'exobrain.assistant.workspaceView',
      JSON.stringify({
        mode: 'chat',
        explorerRoute: { type: 'overview' },
        expandedCategories: {}
      })
    );

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2025/01/14', message_count: 1 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }, { reference: '2025/01/14' }]));

    render(Page);

    await waitFor(() => {
      expect(screen.getByText('Journal:')).toBeInTheDocument();
      expect(screen.getAllByText('2025/01/14').length).toBeGreaterThan(0);
      expect(screen.getByText('cached')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Switch to Knowledge Explorer' })).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalledWith('/api/journal/2025/01/14', undefined);
  });

  it('restores last explorer location from session storage in knowledge mode', async () => {
    window.sessionStorage.setItem(
      'exobrain.assistant.session',
      JSON.stringify({
        user: { name: 'Test User', email: 'test.user@exobrain.local' },
        journalReference: '2026/02/19',
        messageCount: 0,
        messages: []
      })
    );
    window.sessionStorage.setItem(
      'exobrain.assistant.workspaceView',
      JSON.stringify({
        mode: 'knowledge',
        explorerRoute: { type: 'category', id: 'cat-1' },
        expandedCategories: { 'cat-1': true }
      })
    );

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          categories: [{ category_id: 'cat-1', display_name: 'Category 1', page_count: 1, sub_categories: [] }]
        })
      )
      .mockResolvedValueOnce(jsonResponse({ knowledge_pages: [{ id: 'page-1', title: 'Page 1', summary: null }] }))
      .mockResolvedValueOnce(jsonResponse({ knowledge_pages: [{ id: 'page-1', title: 'Page 1', summary: null }] }));

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Switch to Journal Chat' })).toBeInTheDocument();
      expect(screen.getByLabelText('Knowledge explorer')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Category 1/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Page 1' })).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/category/cat-1/pages', undefined);
  });

  it('renders update button in header with default tooltip when updates are available', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 1 }))
      .mockResolvedValueOnce(
        jsonResponse([{ id: 'm1', role: 'assistant', content: 'server hello', sequence: 1 }])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]));

    render(Page);

    await waitFor(() => {
      const updateButton = screen.getByRole('button', { name: 'Update knowledge base' });
      expect(updateButton).toBeEnabled();
      expect(updateButton).toHaveAttribute('title', 'Update knowledge base');
    });
  });

  it('disables knowledge update and shows nothing-to-update tooltip when no new today messages', async () => {
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
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]));

    render(Page);

    await waitFor(() => {
      const updateButton = screen.getByRole('button', { name: 'Update knowledge base' });
      expect(updateButton).toBeDisabled();
      expect(updateButton).toHaveClass('knowledge-update-trigger');
      expect(updateButton).toHaveAttribute('title', 'nothing to update');
    });
  });

  it('enqueues knowledge update, opens watch stream, spins during status, then settles on success', async () => {
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

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' }))
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'server hello', sequence: 2 },
          { id: 'm2', role: 'user', content: 'server hi', sequence: 1 }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-123' }));

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Update knowledge base' })).toBeEnabled();
    });

    const updateButton = screen.getByRole('button', { name: 'Update knowledge base' });
    await fireEvent.click(updateButton);

    await waitFor(() => {
      expect(updateButton).toBeDisabled();
      expect(updateButton).toHaveAttribute('title', 'Knowledge update in progress');
      expect(updateButton.querySelector('svg')).toHaveClass('spinning');
    });

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    const source = MockEventSource.latest!;
    expect(source.url).toBe('/api/knowledge/update/job-123/watch');

    source.emit('status', {
      job_id: 'job-123',
      state: 'STARTED',
      attempt: 1,
      detail: 'working',
      terminal: false,
      emitted_at: '2026-02-19T00:00:00Z'
    });

    await waitFor(() => {
      expect(updateButton.querySelector('svg')).toHaveClass('spinning');
    });

    source.emit('done', { job_id: 'job-123', state: 'SUCCEEDED', terminal: true });

    await waitFor(() => {
      expect(updateButton).toBeDisabled();
      expect(updateButton).toHaveAttribute('title', 'nothing to update');
      expect(updateButton.querySelector('svg')).not.toHaveClass('spinning');
      const successNotice = screen.getByText('Knowledge base updated successfully.');
      expect(successNotice).toBeInTheDocument();
      expect(successNotice).toHaveAttribute('role', 'status');
      expect(successNotice).toHaveAttribute('aria-live', 'polite');
      expect(source.close).toHaveBeenCalledTimes(1);
    });
  });

  it('stops spinner and shows alert when knowledge update ends in terminal failure', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'server hello', sequence: 2 },
          { id: 'm2', role: 'user', content: 'server hi', sequence: 1 }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-123' }));

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Update knowledge base' })).toBeEnabled();
    });

    const updateButton = screen.getByRole('button', { name: 'Update knowledge base' });
    await fireEvent.click(updateButton);

    const source = MockEventSource.latest!;
    source.emit('status', { job_id: 'job-123', state: 'STARTED', attempt: 1, detail: 'working', terminal: false, emitted_at: '2026-02-19T00:00:00Z' });
    source.emit('done', { job_id: 'job-123', state: 'FAILED', terminal: true });

    await waitFor(() => {
      const errorNotice = screen.getByText('Could not update knowledge base. Please try again.');
      expect(errorNotice).toBeInTheDocument();
      expect(errorNotice).toHaveAttribute('role', 'alert');
      expect(updateButton.querySelector('svg')).not.toHaveClass('spinning');
      expect(source.close).toHaveBeenCalledTimes(1);
    });
  });

  it('stops spinner and shows alert when knowledge update watch transport fails', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'server hello', sequence: 2 },
          { id: 'm2', role: 'user', content: 'server hi', sequence: 1 }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-123' }));

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Update knowledge base' })).toBeEnabled();
    });

    const updateButton = screen.getByRole('button', { name: 'Update knowledge base' });
    await fireEvent.click(updateButton);

    const source = MockEventSource.latest!;
    source.emit('status', { job_id: 'job-123', state: 'STARTED', attempt: 1, detail: 'working', terminal: false, emitted_at: '2026-02-19T00:00:00Z' });
    source.onerror?.(new Event('error'));

    await waitFor(() => {
      const errorNotice = screen.getByText('Could not update knowledge base. Please try again.');
      expect(errorNotice).toBeInTheDocument();
      expect(errorNotice).toHaveAttribute('role', 'alert');
      expect(updateButton.querySelector('svg')).not.toHaveClass('spinning');
      expect(source.close).toHaveBeenCalledTimes(1);
    });
  });

  it('closes knowledge update watch stream on logout and on unmount cleanup', async () => {
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
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19', message_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          { id: 'm1', role: 'assistant', content: 'server hello', sequence: 2 },
          { id: 'm2', role: 'user', content: 'server hi', sequence: 1 }
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ reference: '2026/02/19' }))
      .mockResolvedValueOnce(jsonResponse([{ reference: '2026/02/19' }]))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-logout' }))
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
      .mockResolvedValueOnce(jsonResponse({}, 204));

    const { unmount } = render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Update knowledge base' })).toBeEnabled();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Update knowledge base' }));

    const source = MockEventSource.latest!;
    await waitFor(() => {
      expect(source.url).toBe('/api/knowledge/update/job-logout/watch');
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(source.close).toHaveBeenCalledTimes(1);
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
    });

    unmount();
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
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
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
      .mockResolvedValueOnce(jsonResponse({ configs: [] }))
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
    window.sessionStorage.setItem(
      'exobrain.assistant.workspaceView',
      JSON.stringify({
        mode: 'knowledge',
        explorerRoute: { type: 'category', id: 'cat-1' },
        expandedCategories: { 'cat-1': true }
      })
    );

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const rawUrl = typeof input === 'string' ? input : String((input as { url?: unknown }).url ?? input);
      
      if (rawUrl.includes('/api/users/me/configs')) {
        return jsonResponse({ configs: [] });
      }

      if (rawUrl.includes('/api/users/me')) {
        return jsonResponse({ name: 'Test User', email: 'test.user@exobrain.local' });
      }

      if (rawUrl.includes('/api/journal/2026/01/01') || rawUrl.includes('/api/journal/2026%2F01%2F01')) {
        return jsonResponse({ reference: '2026/01/01', message_count: 0 });
      }

      if (rawUrl.includes('/api/journal/today')) {
        return jsonResponse({ reference: '2026/02/19' });
      }

      if (rawUrl.includes('/api/journal')) {
        return jsonResponse([{ reference: '2026/02/19' }, { reference: '2026/01/01' }]);
      }

      if (rawUrl.includes('/api/knowledge/category/cat-1/pages')) {
        return jsonResponse({ knowledge_pages: [{ id: 'page-1', title: 'Page 1', summary: null }] });
      }

      if (rawUrl.includes('/api/knowledge/category')) {
        return jsonResponse({
          categories: [{ category_id: 'cat-1', display_name: 'Category 1', page_count: 1, sub_categories: [] }]
        });
      }

      if (rawUrl.includes('/api/auth/logout')) {
        return { ok: true, status: 204 } as Response;
      }

      return jsonResponse({}, 404);
    });

    render(Page);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Open user menu' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
      expect(window.sessionStorage.getItem('exobrain.assistant.session')).toBeNull();
      expect(window.sessionStorage.getItem('exobrain.assistant.workspaceView')).toBeNull();
    });
  });
});
