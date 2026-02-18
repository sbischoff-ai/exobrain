import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ChatView from './ChatView.svelte';

function createStreamingResponse(chunks) {
  const encoder = new TextEncoder();
  let index = 0;

  return {
    ok: true,
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) {
              return { done: true, value: undefined };
            }
            const value = encoder.encode(chunks[index]);
            index += 1;
            return { done: false, value };
          }
        };
      }
    }
  };
}

describe('ChatView', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('streams backend chunks into the assistant reply and appends user message', async () => {
    // This test verifies the full happy path: submit user input, stream response chunks,
    // and ensure rendered output reflects the incremental assistant response.
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      createStreamingResponse(['Hello', ' ', 'from tests'])
    );

    render(ChatView);

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Test prompt' } });
    await fireEvent.submit(input.closest('form'));

    await waitFor(() => {
      expect(screen.getByText('Test prompt')).toBeInTheDocument();
      expect(screen.getByText('Hello from tests')).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'Test prompt' })
    });
  });

  it('shows a clear error notice when backend request fails', async () => {
    // This test checks resilience: when fetch rejects, UI should both notify the user
    // and inject a fallback assistant message instead of staying empty/spinning forever.
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network down'));

    render(ChatView);

    const input = screen.getByLabelText('Type your message');
    await fireEvent.input(input, { target: { value: 'Will this fail?' } });
    await fireEvent.submit(input.closest('form'));

    await waitFor(() => {
      expect(
        screen.getByText('Could not reach the assistant backend. Please try again.')
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        'Sorry, I could not generate a response because the connection failed.'
      )
    ).toBeInTheDocument();
  });
});
