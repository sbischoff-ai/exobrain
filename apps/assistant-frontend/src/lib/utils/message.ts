import type { JournalMessage, StoredMessage } from '$lib/models/journal';

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
    makeClientMessageId()
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
