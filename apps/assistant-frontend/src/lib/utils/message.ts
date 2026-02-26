import type { JournalMessage, JournalToolCall, ProcessInfo, StoredMessage } from '$lib/models/journal';


const toProcessInfo = (toolCall: JournalToolCall): ProcessInfo => {
  if (typeof toolCall.error === 'string' && toolCall.error.length > 0) {
    return {
      id: makeClientMessageId(),
      toolCallId: toolCall.tool_call_id,
      title: toolCall.title,
      description: toolCall.error,
      state: 'error'
    };
  }

  if (typeof toolCall.response === 'string' && toolCall.response.length > 0) {
    return {
      id: makeClientMessageId(),
      toolCallId: toolCall.tool_call_id,
      title: toolCall.title,
      description: toolCall.description,
      response: toolCall.response,
      state: 'resolved'
    };
  }

  return {
    id: makeClientMessageId(),
    toolCallId: toolCall.tool_call_id,
    title: toolCall.title,
    description: toolCall.description,
    state: 'pending'
  };
};

const toProcessInfos = (toolCalls: unknown): ProcessInfo[] | undefined => {
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
    return undefined;
  }

  const validCalls = toolCalls.filter((item): item is JournalToolCall => {
    if (!item || typeof item !== 'object') {
      return false;
    }

    const maybeCall = item as JournalToolCall;
    return (
      typeof maybeCall.tool_call_id === 'string' &&
      typeof maybeCall.title === 'string' &&
      typeof maybeCall.description === 'string'
    );
  });

  if (!validCalls.length) {
    return undefined;
  }

  return validCalls.map(toProcessInfo);
};

/** Generate a client idempotency key for outgoing chat messages. */
export const makeClientMessageId = (): string =>
  globalThis?.crypto?.randomUUID?.() ?? `client-${Date.now()}-${Math.floor(Math.random() * 100000)}`;

/** Normalize backend message payloads into session-storable frontend messages. */
export const toStoredMessage = (message: Partial<JournalMessage> & { clientMessageId?: string; client_message_id?: string }): StoredMessage => ({
  role: (message.role as string) ?? 'assistant',
  content: typeof message.content === 'string' ? message.content : '',
  clientMessageId:
    (message.clientMessageId as string | undefined) ??
    (message.client_message_id as string | undefined) ??
    (message.id as string | undefined) ??
    makeClientMessageId(),
  createdAt: typeof message.created_at === 'string' ? message.created_at : undefined,
  sequence: typeof message.sequence === 'number' ? message.sequence : undefined,
  toolCalls: Array.isArray(message.tool_calls) ? message.tool_calls : undefined,
  processInfos: toProcessInfos(message.tool_calls)
});

/**
 * Convert API messages into chronological (oldest -> newest) UI order.
 * Backend returns newest-first for cursor pagination efficiency.
 */
export const toChronologicalStoredMessages = (rows: JournalMessage[]): StoredMessage[] =>
  [...rows]
    .sort((left, right) => {
      if (left.sequence == null && right.sequence == null) {
        return 0;
      }
      if (left.sequence == null) {
        return -1;
      }
      if (right.sequence == null) {
        return 1;
      }
      return left.sequence - right.sequence;
    })
    .map(toStoredMessage);

export const toStoredMessages = toChronologicalStoredMessages;
