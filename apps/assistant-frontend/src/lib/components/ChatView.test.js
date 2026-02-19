import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ChatView from './ChatView.svelte';

describe('ChatView', () => {
  it('renders journal reference and messages', () => {
    render(ChatView, {
      props: {
        reference: '2026/02/19',
        messages: [
          { role: 'assistant', content: 'Hello there' },
          { role: 'user', content: 'Hi' }
        ]
      }
    });

    expect(screen.getByText('Journal:')).toBeInTheDocument();
    expect(screen.getByText('2026/02/19')).toBeInTheDocument();
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByText('Hi')).toBeInTheDocument();
  });

  it('calls onSend on submit', async () => {
    const sent = [];
    render(ChatView, { props: { messages: [], onSend: (text) => sent.push(text) } });

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Test prompt' } });
    await fireEvent.submit(input.closest('form'));

    expect(sent).toEqual(['Test prompt']);
  });
});
