import { describe, expect, it } from 'vitest';

import { toChronologicalStoredMessages } from '$lib/utils/message';

describe('message utils', () => {
  it('orders API messages by ascending sequence for UI rendering', () => {
    const messages = toChronologicalStoredMessages([
      { id: 'm3', role: 'assistant', content: 'newest', sequence: 3 },
      { id: 'm2', role: 'user', content: 'middle', sequence: 2 },
      { id: 'm1', role: 'assistant', content: 'oldest', sequence: 1 }
    ]);

    expect(messages.map((message) => message.content)).toEqual(['oldest', 'middle', 'newest']);
  });



  it('maps created_at to createdAt for UI timestamp labels', () => {
    const [message] = toChronologicalStoredMessages([
      { id: 'm1', role: 'assistant', content: 'timed', sequence: 1, created_at: '2026-01-02T03:04:05Z' }
    ]);

    expect(message.createdAt).toBe('2026-01-02T03:04:05Z');
  });

  it('maps persisted tool_calls into process info boxes', () => {
    const [assistantMessage] = toChronologicalStoredMessages([
      {
        id: 'm1',
        role: 'assistant',
        content: 'with tools',
        sequence: 1,
        tool_calls: [
          {
            tool_call_id: 'tc-1',
            title: 'Web search',
            description: 'Searching',
            response: 'Found sources',
            error: null
          },
          {
            tool_call_id: 'tc-2',
            title: 'Web fetch',
            description: 'Fetching',
            response: null,
            error: 'Failed to fetch'
          }
        ]
      }
    ]);

    expect(assistantMessage.toolCalls).toHaveLength(2);
    expect(assistantMessage.processInfos?.map((item) => ({ title: item.title, description: item.description, response: item.response, state: item.state }))).toEqual([
      { title: 'Web search', description: 'Searching', response: 'Found sources', state: 'resolved' },
      { title: 'Web fetch', description: 'Failed to fetch', response: undefined, state: 'error' }
    ]);
  });
});
