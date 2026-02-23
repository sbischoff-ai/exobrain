import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import ChatView from './ChatView.svelte';

describe('ChatView', () => {

  it('renders assistant process info labels', () => {
    render(ChatView, {
      props: {
        messages: [
          {
            role: 'assistant',
            content: 'Hello',
            clientMessageId: 'a-1',
            processInfos: [
              { id: 'p-1', title: 'Web search', description: 'Searching', state: 'pending' },
              { id: 'p-2', title: 'Error', description: 'Failed', state: 'error' }
            ]
          }
        ]
      }
    });

    expect(screen.getByText('Web search')).toBeInTheDocument();
    expect(screen.getByText('Searching...')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders journal reference and messages', () => {
    render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'assistant', content: 'Hello there', clientMessageId: 'a-1' },
          { role: 'user', content: 'Hi', clientMessageId: 'u-1' }
        ]
      }
    });

    expect(screen.getByText('Journal:')).toBeInTheDocument();
    expect(screen.getByText('2026/02/19')).toBeInTheDocument();
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByText('Hi')).toBeInTheDocument();
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

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(0);
    });

    const baselineCalls = scrollSpy.mock.calls.length;
    const input = screen.getByLabelText('Type your message');

    await fireEvent.input(input, { target: { value: 'H' } });
    await fireEvent.input(input, { target: { value: 'He' } });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBe(baselineCalls);
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
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(callsAfterInitialRender + 1);
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
      expect(scrollSpy.mock.calls.length).toBe(callsDuringStreaming + 1);
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
