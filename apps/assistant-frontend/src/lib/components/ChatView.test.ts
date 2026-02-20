import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import ChatView from './ChatView.svelte';

describe('ChatView', () => {
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

  it('calls onSend on submit', async () => {
    const sent: string[] = [];
    render(ChatView, { props: { messages: [], onSend: (text: string) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Test prompt' } });
    await fireEvent.submit(input.closest('form')!);

    expect(sent).toEqual(['Test prompt']);
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
      messages: [
        { role: 'assistant', content: 'First', clientMessageId: 'a-1' },
        { role: 'user', content: 'Second', clientMessageId: 'u-1' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy).toHaveBeenCalled();
    });
  });

  it('keeps auto-scrolling while streamed assistant content grows', async () => {
    const scrollSpy = vi.spyOn(HTMLElement.prototype, 'scrollTo');

    const { rerender } = render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
          { role: 'assistant', content: 'a', clientMessageId: 'a-1' }
        ]
      }
    });

    const callsAfterInitialRender = scrollSpy.mock.calls.length;

    await rerender({
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'ab', clientMessageId: 'a-1' }
      ]
    });

    await rerender({
      messages: [
        { role: 'user', content: 'Prompt', clientMessageId: 'u-1' },
        { role: 'assistant', content: 'abc', clientMessageId: 'a-1' }
      ]
    });

    await waitFor(() => {
      expect(scrollSpy.mock.calls.length).toBeGreaterThan(callsAfterInitialRender + 1);
    });
  });
});
