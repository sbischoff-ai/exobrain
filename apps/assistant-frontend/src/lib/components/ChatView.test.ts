import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import ChatView from './ChatView.svelte';

describe('ChatView', () => {

  it('renders assistant process info labels and toggles card stack', async () => {
    render(ChatView, {
      props: {
        messages: [
          {
            role: 'assistant',
            content: 'Hello',
            clientMessageId: 'a-1',
            processInfos: [
              { id: 'p-1', title: 'Web search', description: 'Searching', state: 'pending' },
              { id: 'p-2', title: 'Web fetch', description: 'Fetching', response: 'Done', state: 'resolved' },
              { id: 'p-3', title: 'Error', description: 'Failed', state: 'error' },
              { id: 'p-4', title: 'Calendar', description: 'Booked', response: 'Confirmed', state: 'resolved' }
            ]
          }
        ]
      }
    });

    expect(screen.getByRole('button', { name: 'Unfold tool call cards' })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Unfold tool call cards' }));
    expect(screen.getByRole('button', { name: 'Fold tool call cards' })).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Confirmed')).toBeInTheDocument();

    const expandedTitles = Array.from(document.querySelectorAll('.process-info-list.expanded .process-title')).map(
      (node) => node.textContent?.trim()
    );
    expect(expandedTitles).toEqual(['Web search', 'Web fetch', 'Error', 'Calendar']);

    await fireEvent.click(screen.getByRole('button', { name: 'Fold tool call cards' }));
    expect(screen.getByRole('button', { name: 'Unfold tool call cards' })).toBeInTheDocument();
  });

  it('renders journal reference, messages, and message timestamps', () => {
    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          {
            role: 'assistant',
            content: 'Hello there',
            clientMessageId: 'a-1',
            createdAt: '2026-02-19T08:07:00Z'
          },
          { role: 'user', content: 'Hi', clientMessageId: 'u-1', createdAt: '2026-02-19T08:09:00Z' }
        ]
      }
    });

    expect(screen.getByText('Journal:')).toBeInTheDocument();
    expect(screen.getByText('2026/02/19')).toBeInTheDocument();
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByText('Hi')).toBeInTheDocument();

    const timeLabels = Array.from(container.querySelectorAll('.message-time')).map((node) => node.textContent?.trim());
    expect(timeLabels).toHaveLength(2);
    expect(timeLabels[0]).toMatch(/^\d{2}:\d{2}$/);
    expect(timeLabels[1]).toMatch(/^\d{2}:\d{2}$/);
    expect(container.querySelector('.message-time.user-time')).toBeTruthy();
  });


  it('renders markdown for user messages', () => {
    render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'user', content: '**Bold user text**', clientMessageId: 'u-1' }]
      }
    });

    expect(screen.getByText('Bold user text')).toBeInTheDocument();
    expect(screen.getByText('Bold user text').tagName).toBe('STRONG');
  });




  it('renders KaTeX math and Mermaid diagram blocks', async () => {
    const markdown = [
      'Inline math $a^2 + b^2 = c^2$.',
      '',
      '$$\\int_0^1 x^2 dx = \\frac{1}{3}$$',
      '',
      '```mermaid',
      'flowchart TD',
      'A[Start] --> B[Done]',
      '```'
    ].join('\n');

    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: markdown, clientMessageId: 'a-math-mermaid-1' }]
      }
    });

    await waitFor(() => {
      expect(container.querySelector('.katex')).toBeTruthy();
      expect(container.querySelector('[data-streamdown-mermaid]')).toBeTruthy();
    });
  });

  it('preserves line breaks in fenced code blocks', async () => {
    const codeBlockMessage = '```ts\nconst status = "ready";\nconsole.log(status);\n```';

    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: codeBlockMessage, clientMessageId: 'a-code-1' }]
      }
    });

    const codeRoot = container.querySelector('.exo-md-code');
    const codePre = container.querySelector('.exo-md-code-pre');
    const codeLines = container.querySelectorAll('.exo-md-code-pre code > span');
    expect(codeRoot).toBeTruthy();
    expect(codePre).toBeTruthy();
    expect(codePre?.textContent).toContain('const status = "ready";');
    expect(codePre?.textContent).toContain('console.log(status);');
    expect(codeLines.length).toBeGreaterThan(1);
  });


  it('preserves empty lines inside fenced code blocks', async () => {
    const codeBlockMessage = '```ts\nconst alpha = 1;\n\nconst beta = 2;\n```';

    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: codeBlockMessage, clientMessageId: 'a-code-2' }]
      }
    });

    const codePre = container.querySelector('.exo-md-code-pre');
    const codeLines = Array.from(container.querySelectorAll('.exo-md-code-pre code > span'));
    expect(codePre).toBeTruthy();
    expect(codeLines.length).toBeGreaterThanOrEqual(3);
    const normalizedMiddleLine = (codeLines[1]?.textContent || '').replace(/\u200b/g, '').trim();
    expect(normalizedMiddleLine).toBe('');
  });


  it('renders paragraph breaks inside list items', async () => {
    const markdown = `- list item 1

  extra paragraph
- list item 2`;

    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: markdown, clientMessageId: 'a-list-1' }]
      }
    });

    const firstListItem = container.querySelector('li');
    expect(firstListItem).toBeTruthy();
    const firstText = firstListItem?.textContent || '';
    expect(firstText).toContain('list item 1');
    expect(firstText).toContain('extra paragraph');
  });


  it('adds spacing between markdown paragraphs', async () => {
    const markdown = 'First paragraph.\n\nSecond paragraph.';

    const { container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: markdown, clientMessageId: 'a-para-1' }]
      }
    });

    const paragraphs = container.querySelectorAll('.assistant-markdown p');
    expect(paragraphs.length).toBeGreaterThanOrEqual(2);
    expect(paragraphs[1]?.textContent).toContain('Second paragraph.');
  });

  it('does not auto-scroll while user types in input', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: 'Hello there', clientMessageId: 'a-1' }]
      }
    });

    const baselineCalls = scrollSpy.mock.calls.length;
    const input = screen.getByLabelText('Type your message');

    await fireEvent.input(input, { target: { value: 'H' } });
    await fireEvent.input(input, { target: { value: 'He' } });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeLessThanOrEqual(baselineCalls + 1);
    });
  });


  it('calls onSend on submit', async () => {
    const sent: string[] = [];
    render(ChatView, { props: { messages: [], onSend: (text: string) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Test prompt' } });
    await fireEvent.submit(input.closest('form')!);

    expect(sent).toEqual(['Test prompt']);
  });


  it('submits on Enter without Shift', async () => {
    const sent: string[] = [];
    render(ChatView, { props: { messages: [], onSend: (text: string) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Line one' } });
    await fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: false });

    expect(sent).toEqual(['Line one']);
  });

  it('allows Shift+Enter for multiline input and sends preserved line breaks', async () => {
    const sent: string[] = [];
    render(ChatView, { props: { messages: [], onSend: (text: string) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Line one\nLine two' } });
    await fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true });
    await fireEvent.submit(input.closest('form')!);

    expect(sent).toEqual(['Line one\nLine two']);
  });

  it('grows composer height up to three lines', async () => {
    render(ChatView, { props: { messages: [] } });

    const input = screen.getByLabelText('Type your message') as HTMLTextAreaElement;

    Object.defineProperty(input, 'scrollHeight', {
      configurable: true,
      get() {
        return 120;
      }
    });

    await fireEvent.input(input, { target: { value: 'One\nTwo\nThree' } });

    expect(input.style.height).toBe('120px');
  });

  it('resets composer height to one line after submit', async () => {
    const sent: string[] = [];
    render(ChatView, { props: { messages: [], onSend: (text: string) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message') as HTMLTextAreaElement;

    Object.defineProperty(input, 'scrollHeight', {
      configurable: true,
      get() {
        return 120;
      }
    });

    await fireEvent.input(input, { target: { value: 'One\nTwo\nThree' } });
    expect(input.style.height).toBe('120px');

    await fireEvent.submit(input.closest('form')!);

    expect(sent).toEqual(['One\nTwo\nThree']);
    expect(input.style.height).toBe('');
  });

  it('shows tooltip when chat controls are disabled for a past journal', () => {
    render(ChatView, {
      props: {
        inputDisabled: true,
        disabledReason: 'You can not chat with past journals.'
      }
    });

    expect(screen.getByLabelText('Type your message')).toHaveAttribute('title', 'You can not chat with past journals.');
    expect(screen.getByRole('button', { name: 'Send message' })).toHaveAttribute('title', 'You can not chat with past journals.');
  });

  it('calls onLoadOlder when user clicks load older messages', async () => {
    const onLoadOlder = vi.fn();

    render(ChatView, {
      props: {
        messages: [{ role: 'assistant', content: 'hello', clientMessageId: 'a-1' }],
        canLoadOlder: true,
        onLoadOlder
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Load older messages' }));

    expect(onLoadOlder).toHaveBeenCalledTimes(1);
  });

  it('scrolls to bottom when new messages are rendered', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: 'First', clientMessageId: 'a-1' }]
      }
    });

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'assistant', content: 'First', clientMessageId: 'a-1' },
        { role: 'user', content: 'Second', clientMessageId: 'u-1' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy).toHaveBeenCalled();
    });
  });

  it('preserves scroll position when older messages are prepended', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const originalScrollTop = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollTop');
    const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollHeight');

    const scrollState = {
      scrollTop: 120,
      scrollHeight: 500
    };
    let prependPhase = false;
    let prependPhaseScrollHeightReads = 0;

    try {
      Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
        configurable: true,
        get() {
          return scrollState.scrollTop;
        },
        set(value: number) {
          scrollState.scrollTop = value;
        }
      });

      Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
        configurable: true,
        get() {
          if (!prependPhase) {
            return scrollState.scrollHeight;
          }

          prependPhaseScrollHeightReads += 1;
          return prependPhaseScrollHeightReads === 1 ? 800 : 900;
        }
      });

      const { rerender } = render(ChatView, {
        props: {
          reference: '2026/02/19',
          messages: [{ role: 'assistant', content: 'newest', clientMessageId: 'a-2' }]
        }
      });

      await waitFor(() => {
        expect(scrollSpy).toHaveBeenCalled();
      });

      const initialScrollCalls = scrollSpy.mock.calls.length;

      scrollState.scrollTop = 80;
      prependPhase = true;

      await rerender({
        reference: '2026/02/19',
        messages: [
          { role: 'assistant', content: 'older', clientMessageId: 'a-1' },
          { role: 'assistant', content: 'newest', clientMessageId: 'a-2' }
        ]
      });

      await waitFor(() => {
        expect(scrollSpy.mock.calls.length).toBe(initialScrollCalls);
        expect(scrollState.scrollTop).toBe(180);
      });
    } finally {
      if (originalScrollTop) {
        Object.defineProperty(HTMLElement.prototype, 'scrollTop', originalScrollTop);
      }
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeight);
      }
    }
  });


  it('auto-scrolls to bottom after loading finishes on initial today journal open', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        loading: true,
        messages: [
          { role: 'assistant', content: 'today earliest', clientMessageId: 'today-1' },
          { role: 'assistant', content: 'today latest', clientMessageId: 'today-2' }
        ]
      }
    });

    const baselineCalls = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      loading: false,
      messages: [
        { role: 'assistant', content: 'today earliest', clientMessageId: 'today-1' },
        { role: 'assistant', content: 'today latest', clientMessageId: 'today-2' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(baselineCalls);
    });
  });

  it('auto-scrolls to bottom when journal reference changes', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2025/01/14',
        canLoadOlder: false,
        messages: [
          { role: 'assistant', content: 'old journal msg', clientMessageId: 'old-1' },
          { role: 'user', content: 'old journal reply', clientMessageId: 'old-2' }
        ]
      }
    });

    const baselineCalls = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      canLoadOlder: true,
      messages: [
        { role: 'assistant', content: 'today earliest', clientMessageId: 'today-1' },
        { role: 'assistant', content: 'today latest', clientMessageId: 'today-2' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(baselineCalls);
    });
  });




  it('auto-scrolls on journal switch even after auto-scroll suspension', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender, container } = render(ChatView, {
      props: {
        reference: '2025/01/14',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'partial stream', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      }
    });

    const messagesContainer = container.querySelector('.messages') as HTMLDivElement;
    await fireEvent.wheel(messagesContainer, { deltaY: -20 });

    const baselineCalls = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'assistant', content: 'today earliest', clientMessageId: 'today-1' },
        { role: 'assistant', content: 'today latest', clientMessageId: 'today-2' }
      ],
      streamingInProgress: false
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(baselineCalls);
    });
  });

  it('jumps to latest when a new user message is appended while scrolled up', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [{ role: 'assistant', content: 'older', clientMessageId: 'a-1' }]
      }
    });

    const baseline = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'assistant', content: 'older', clientMessageId: 'a-1' },
        { role: 'user', content: 'new prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: '', clientMessageId: 'a-2' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(baseline);
    });
  });

  it('stops auto-scrolling for the current stream when user scrolls up', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender, container } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'first', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      }
    });

    const messagesContainer = container.querySelector('.messages') as HTMLDivElement;
    await fireEvent.wheel(messagesContainer, { deltaY: -15 });

    const baselineCalls = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'first second', clientMessageId: 'a-1' }
      ],
      streamingInProgress: true
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBe(baselineCalls);
    });
  });


  it('resumes auto-scroll during the same stream after user returns to bottom', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const originalScrollTop = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollTop');
    const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollHeight');
    const originalClientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight');

    const scrollState = {
      scrollTop: 100,
      scrollHeight: 1000,
      clientHeight: 500
    };

    try {
      Object.defineProperty(HTMLElement.prototype, 'scrollTop', {
        configurable: true,
        get() {
          return scrollState.scrollTop;
        },
        set(value: number) {
          scrollState.scrollTop = value;
        }
      });

      Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
        configurable: true,
        get() {
          return scrollState.scrollHeight;
        }
      });

      Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
        configurable: true,
        get() {
          return scrollState.clientHeight;
        }
      });

      const { rerender, container } = render(ChatView, {
        props: {
          reference: '2026/02/19',
          messages: [
            { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
            { role: 'assistant', content: 'first', clientMessageId: 'a-1' }
          ],
          streamingInProgress: true
        }
      });

      const messagesContainer = container.querySelector('.messages') as HTMLDivElement;
      await fireEvent.wheel(messagesContainer, { deltaY: -20 });

      const callsAfterPause = scrollSpy.mock.calls.length;

      await rerender({
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'first second', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      });

      await waitFor(() => {
        expect(scrollSpy.mock.calls.length).toBe(callsAfterPause);
      });

      scrollState.scrollTop = 500;
      await fireEvent.scroll(messagesContainer);

      scrollState.scrollHeight = 1200;
      await rerender({
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'first second third', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      });

      await waitFor(() => {
        expect(scrollSpy.mock.calls.length).toBeGreaterThan(callsAfterPause);
      });
    } finally {
      if (originalScrollTop) {
        Object.defineProperty(HTMLElement.prototype, 'scrollTop', originalScrollTop);
      }
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeight);
      }
      if (originalClientHeight) {
        Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeight);
      }
    }
  });

  it('keeps auto-scrolling while streamed assistant content grows', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'a', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      }
    });

    const callsAfterInitialRender = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'ab', clientMessageId: 'a-1' }
      ],
      streamingInProgress: true
    });

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'abc', clientMessageId: 'a-1' }
      ],
      streamingInProgress: true
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(callsAfterInitialRender);
    });
  });

  it('stops auto-scrolling after stream ends when already at bottom', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'streaming text', clientMessageId: 'a-1' }
        ],
        streamingInProgress: true
      }
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(0);
    });

    const callsDuringStreaming = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'streaming text done', clientMessageId: 'a-1' }
      ],
      streamingInProgress: false
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThanOrEqual(callsDuringStreaming);
    });

    const callsAfterDone = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2026/02/19',
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'streaming text done', clientMessageId: 'a-1' }
      ],
      streamingInProgress: false
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBe(callsAfterDone);
    });
  });

  it('does not auto-scroll when autoScrollEnabled is false', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2025/01/14',
        autoScrollEnabled: false,
        messages: [{ role: 'assistant', content: 'older', clientMessageId: 'a-1' }]
      }
    });

    const baselineCalls = scrollSpy.mock.calls.length;

    await rerender({
      reference: '2025/01/14',
      autoScrollEnabled: false,
      messages: [
        { role: 'assistant', content: 'older', clientMessageId: 'a-1' },
        { role: 'assistant', content: 'older-2', clientMessageId: 'a-2' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBe(baselineCalls);
    });
  });
});
