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
});
