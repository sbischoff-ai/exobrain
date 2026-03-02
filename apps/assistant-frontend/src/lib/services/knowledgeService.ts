import type {
  KnowledgeUpdateDoneEvent,
  KnowledgeUpdateResponse,
  KnowledgeUpdateStatusEvent,
  ParsedKnowledgeUpdateStreamEvent
} from '$lib/models/knowledge';
import { apiClient } from '$lib/services/apiClient';

interface EnqueueUpdateRequest {
  journal_reference?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isKnowledgeUpdateStatusEvent(value: unknown): value is KnowledgeUpdateStatusEvent {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.job_id === 'string' &&
    typeof value.state === 'string' &&
    typeof value.attempt === 'number' &&
    typeof value.detail === 'string' &&
    typeof value.terminal === 'boolean' &&
    typeof value.emitted_at === 'string'
  );
}

function isKnowledgeUpdateDoneEvent(value: unknown): value is KnowledgeUpdateDoneEvent {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.job_id === 'string' && typeof value.state === 'string' && typeof value.terminal === 'boolean';
}

export function parseKnowledgeUpdateStreamEvent(type: string, rawData: string): ParsedKnowledgeUpdateStreamEvent | null {
  let parsed: unknown;

  try {
    parsed = JSON.parse(rawData);
  } catch {
    return null;
  }

  if (type === 'status' && isKnowledgeUpdateStatusEvent(parsed)) {
    return { type: 'status', data: parsed };
  }

  if (type === 'done' && isKnowledgeUpdateDoneEvent(parsed)) {
    return { type: 'done', data: parsed };
  }

  return null;
}

export function isTerminalKnowledgeUpdateState(event: ParsedKnowledgeUpdateStreamEvent): boolean {
  return event.data.terminal;
}

export function isKnowledgeUpdateDoneEventType(event: ParsedKnowledgeUpdateStreamEvent): event is { type: 'done'; data: KnowledgeUpdateDoneEvent } {
  return event.type === 'done';
}

/** Service that exposes knowledge-update API and stream helpers for UI consumption. */
export const knowledgeService = {
  enqueueUpdate(journalReference?: string): Promise<KnowledgeUpdateResponse> {
    const payload: EnqueueUpdateRequest = {};
    if (journalReference !== undefined) {
      payload.journal_reference = journalReference;
    }

    return apiClient<KnowledgeUpdateResponse>('/api/knowledge/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  watchUpdate(jobId: string): EventSource {
    return new EventSource(`/api/knowledge/update/${encodeURIComponent(jobId)}/watch`);
  }
};
