import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  isKnowledgeUpdateDoneEventType,
  isTerminalKnowledgeUpdateState,
  knowledgeService,
  parseKnowledgeUpdateStreamEvent
} from '$lib/services/knowledgeService';

describe('knowledgeService', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts enqueue request without journal_reference when omitted', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ job_id: 'job-1' }), { status: 200 })
    );

    await knowledgeService.enqueueUpdate();

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
  });

  it('posts enqueue request with journal_reference when provided', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ job_id: 'job-1' }), { status: 200 })
    );

    await knowledgeService.enqueueUpdate('jrnl-123');

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ journal_reference: 'jrnl-123' })
    });
  });

  it('parses valid status SSE payloads', () => {
    const event = parseKnowledgeUpdateStreamEvent(
      'status',
      JSON.stringify({
        job_id: 'job-1',
        state: 'running',
        attempt: 2,
        detail: 'processing',
        terminal: false,
        emitted_at: '2026-02-03T04:05:06Z'
      })
    );

    expect(event).toEqual({
      type: 'status',
      data: {
        job_id: 'job-1',
        state: 'running',
        attempt: 2,
        detail: 'processing',
        terminal: false,
        emitted_at: '2026-02-03T04:05:06Z'
      }
    });
    expect(event && isTerminalKnowledgeUpdateState(event)).toBe(false);
  });

  it('parses valid done SSE payloads and identifies terminal events', () => {
    const event = parseKnowledgeUpdateStreamEvent(
      'done',
      JSON.stringify({ job_id: 'job-1', state: 'completed', terminal: true })
    );

    expect(event).toEqual({
      type: 'done',
      data: { job_id: 'job-1', state: 'completed', terminal: true }
    });

    expect(event).not.toBeNull();
    if (!event) {
      throw new Error('expected a parsed done event');
    }

    expect(isKnowledgeUpdateDoneEventType(event)).toBe(true);
    expect(isTerminalKnowledgeUpdateState(event)).toBe(true);
  });

  it('returns null for invalid SSE payloads', () => {
    expect(parseKnowledgeUpdateStreamEvent('status', '{bad-json')).toBeNull();
    expect(
      parseKnowledgeUpdateStreamEvent(
        'status',
        JSON.stringify({ job_id: 'job-1', state: 'running', terminal: false })
      )
    ).toBeNull();
    expect(
      parseKnowledgeUpdateStreamEvent(
        'unknown',
        JSON.stringify({ job_id: 'job-1', state: 'running', terminal: false })
      )
    ).toBeNull();
  });
});
