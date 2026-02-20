import type { JournalEntry, JournalMessage, StoredMessage } from '$lib/models/journal';
import { apiClient } from '$lib/services/apiClient';
import { toStoredMessages } from '$lib/utils/message';

/** Service that exposes journal-oriented API and business logic for UI consumption. */
export const journalService = {
  getToday(create = false): Promise<JournalEntry> {
    const suffix = create ? '?create=true' : '';
    return apiClient<JournalEntry>(`/api/journal/today${suffix}`);
  },

  listEntries(): Promise<JournalEntry[]> {
    return apiClient<JournalEntry[]>('/api/journal');
  },

  getSummary(reference: string): Promise<JournalEntry> {
    return apiClient<JournalEntry>(`/api/journal/${reference}`);
  },

  listMessages(reference: string, cursor?: number, limit = 100): Promise<JournalMessage[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor !== undefined) {
      params.set('cursor', String(cursor));
    }
    return apiClient<JournalMessage[]>(`/api/journal/${reference}/messages?${params.toString()}`);
  },

  listTodayMessages(limit = 100): Promise<JournalMessage[]> {
    return apiClient<JournalMessage[]>(`/api/journal/today/messages?limit=${limit}`);
  },

  async listStoredMessages(reference: string): Promise<StoredMessage[]> {
    const messages = await this.listMessages(reference);
    return toStoredMessages(messages);
  }
};
