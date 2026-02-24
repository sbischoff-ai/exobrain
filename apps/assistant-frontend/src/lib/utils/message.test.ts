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
    expect(assistantMessage.processInfos?.map((item) => ({ title: item.title, description: item.description, state: item.state }))).toEqual([
      { title: 'Web search', description: 'Found sources', state: 'resolved' },
      { title: 'Web fetch', description: 'Failed to fetch', state: 'error' }
    ]);
  });
});
