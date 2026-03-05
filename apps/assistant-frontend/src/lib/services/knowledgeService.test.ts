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

  it('gets and normalizes category tree', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          categories: [
            {
              category_id: 'node.root',
              display_name: 'Root',
              page_count: 3,
              sub_categories: [
                {
                  category_id: 'node.child',
                  display_name: 'Child',
                  sub_categories: []
                }
              ]
            }
          ]
        }),
        { status: 200 }
      )
    );

    const response = await knowledgeService.getCategoryTree();

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/category', undefined);
    expect(response).toEqual({
      categories: [
        {
          id: 'node.root',
          name: 'Root',
          page_count: 3,
          children: [
            {
              id: 'node.child',
              name: 'Child',
              page_count: 0,
              children: []
            }
          ]
        }
      ]
    });
  });

  it('gets and normalizes category pages', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          knowledge_pages: [
            { id: 'entity-1', title: 'Entity One', summary: 'Summary' },
            { id: 'entity-2', title: 'Entity Two' }
          ],
          page_size: 20,
          next_page_token: 'cursor-1',
          total_count: 7
        }),
        { status: 200 }
      )
    );

    const response = await knowledgeService.getCategoryPages('type/with/slash');

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/category/type%2Fwith%2Fslash/pages', undefined);
    expect(response).toEqual({
      pages: [
        { id: 'entity-1', title: 'Entity One', summary: 'Summary' },
        { id: 'entity-2', title: 'Entity Two', summary: null }
      ],
      total_count: 7
    });
  });

  it('gets and normalizes page detail', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'entity-1',
          title: 'Entity One',
          category_id: 'node.child',
          summary: 'Root',
          metadata: {
            created_at: '2026-02-19T09:00:00Z',
            updated_at: '2026-02-19T10:00:00Z'
          },
          links: [{ page_id: 'entity-2', title: 'Entity Two', summary: 'Linked' }],
          content_markdown: 'Root\\n\\nChild',
          category_breadcrumb: [
            { category_id: 'node.root', display_name: 'Root' },
            { category_id: 'node.child', display_name: 'Child' }
          ]
        }),
        { status: 200 }
      )
    );

    const response = await knowledgeService.getPage('entity-1');

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/page/entity-1', undefined);

    expect(response).toEqual({
      id: 'entity-1',
      category_id: 'node.child',
      title: 'Entity One',
      summary: 'Root',
      content_markdown: 'Root\\n\\nChild',
      created_at: '2026-02-19T09:00:00Z',
      updated_at: '2026-02-19T10:00:00Z',
      links: [{ page_id: 'entity-2', title: 'Entity Two', summary: 'Linked' }],
      category_breadcrumb: {
        path: [
          { id: 'node.root', name: 'Root' },
          { id: 'node.child', name: 'Child' }
        ]
      }
    });
  });



  it('normalizes object-shaped category breadcrumb paths', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'entity-7',
          title: 'Entity Seven',
          metadata: {
            created_at: '2026-03-01T08:00:00Z',
            updated_at: '2026-03-01T09:00:00Z'
          },
          links: [],
          content_markdown: 'Content',
          category_id: 'node.task',
          category_breadcrumb: {
            path: [
              { id: 'node.event', name: 'Event' },
              { id: 'node.task', name: 'Task' }
            ]
          }
        }),
        { status: 200 }
      )
    );

    const response = await knowledgeService.getPage('entity-7');

    expect(response.category_id).toBe('node.task');
    expect(response.category_breadcrumb.path).toEqual([
      { id: 'node.event', name: 'Event' },
      { id: 'node.task', name: 'Task' }
    ]);
  });

  it('normalizes top-level page timestamps when metadata is missing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'entity-9',
          title: 'Entity Nine',
          created_at: '2026-03-01T08:00:00Z',
          updated_at: '2026-03-01T09:00:00Z',
          links: [],
          content_markdown: 'Content',
          category_id: 'node.note',
          category_breadcrumb: []
        }),
        { status: 200 }
      )
    );

    const response = await knowledgeService.getPage('entity-9');

    expect(response.category_id).toBe('node.note');
    expect(response.created_at).toBe('2026-03-01T08:00:00Z');
    expect(response.updated_at).toBe('2026-03-01T09:00:00Z');
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

  it('encodes page detail ids with slashes', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'entity/with/slash', title: 'Entity', metadata: {}, links: [] }), {
        status: 200
      })
    );

    await knowledgeService.getPage('entity/with/slash');

    expect(fetchSpy).toHaveBeenCalledWith('/api/knowledge/page/entity%2Fwith%2Fslash', undefined);
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
