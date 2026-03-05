import type {
  KnowledgeCategoryNode,
  KnowledgeCategoryPagesResponse,
  KnowledgeCategoryTreeResponse,
  KnowledgePageCategoryBreadcrumb,
  KnowledgePageDetail,
  KnowledgePageLink,
  KnowledgeUpdateDoneEvent,
  KnowledgeUpdateResponse,
  KnowledgeUpdateStatusEvent,
  ParsedKnowledgeUpdateStreamEvent
} from '$lib/models/knowledge';
import { apiClient } from '$lib/services/apiClient';

interface EnqueueUpdateRequest {
  journal_reference?: string;
}

interface BackendKnowledgeCategoryNode {
  category_id?: unknown;
  display_name?: unknown;
  page_count?: unknown;
  sub_categories?: unknown;
}

interface BackendKnowledgeCategoryTreeResponse {
  categories?: unknown;
}

interface BackendKnowledgeCategoryPagesResponse {
  knowledge_pages?: unknown;
}

interface BackendKnowledgePageDetailResponse {
  id?: unknown;
  title?: unknown;
  summary?: unknown;
  metadata?: unknown;
  links?: unknown;
  content_markdown?: unknown;
  category_breadcrumb?: unknown;
  category_id?: unknown;
  created_at?: unknown;
  updated_at?: unknown;
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


function maybeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function maybeTimestamp(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function isKnowledgeUpdateDoneEvent(value: unknown): value is KnowledgeUpdateDoneEvent {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.job_id === 'string' && typeof value.state === 'string' && typeof value.terminal === 'boolean';
}

function normalizeCategoryNode(value: unknown): KnowledgeCategoryNode | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = typeof value.category_id === 'string' ? value.category_id : null;
  const name = typeof value.display_name === 'string' ? value.display_name : null;
  if (!id || !name) {
    return null;
  }

  const pageCount = typeof value.page_count === 'number' ? value.page_count : 0;
  const rawChildren = Array.isArray(value.sub_categories) ? value.sub_categories : [];

  return {
    id,
    name,
    page_count: pageCount,
    children: rawChildren.map(normalizeCategoryNode).filter((child): child is KnowledgeCategoryNode => child !== null)
  };
}

function normalizeCategoryTreeResponse(value: BackendKnowledgeCategoryTreeResponse): KnowledgeCategoryTreeResponse {
  const categories = Array.isArray(value.categories) ? value.categories : [];
  return {
    categories: categories.map(normalizeCategoryNode).filter((category): category is KnowledgeCategoryNode => category !== null)
  };
}

function normalizeCategoryPagesResponse(value: BackendKnowledgeCategoryPagesResponse): KnowledgeCategoryPagesResponse {
  const pages = Array.isArray(value.knowledge_pages) ? value.knowledge_pages : [];
  const totalCount = maybeNumber((value as Record<string, unknown>).total_count);

  return {
    pages: pages
      .map((page) => {
        if (!isRecord(page)) {
          return null;
        }

        const id = typeof page.id === 'string' ? page.id : null;
        const title = typeof page.title === 'string' ? page.title : null;
        if (!id || !title) {
          return null;
        }

        return {
          id,
          title,
          summary: typeof page.summary === 'string' ? page.summary : null
        };
      })
      .filter((page): page is KnowledgeCategoryPagesResponse['pages'][number] => page !== null),
    total_count: totalCount
  };
}

function normalizePageLink(value: unknown): KnowledgePageLink | null {
  if (!isRecord(value)) {
    return null;
  }

  const pageId = typeof value.page_id === 'string' ? value.page_id : null;
  const title = typeof value.title === 'string' ? value.title : null;
  if (!pageId || !title) {
    return null;
  }

  return {
    page_id: pageId,
    title,
    summary: typeof value.summary === 'string' ? value.summary : null
  };
}

function normalizeCategoryBreadcrumb(value: unknown): KnowledgePageCategoryBreadcrumb {
  const rawPath = Array.isArray(value)
    ? value
    : isRecord(value) && Array.isArray(value.path)
      ? value.path
      : [];

  return {
    path: rawPath
      .map((item) => {
        if (!isRecord(item)) {
          return null;
        }

        const id = typeof item.category_id === 'string' ? item.category_id : typeof item.id === 'string' ? item.id : null;
        const name =
          typeof item.display_name === 'string' ? item.display_name : typeof item.name === 'string' ? item.name : null;
        if (!id || !name) {
          return null;
        }

        return { id, name };
      })
      .filter((item): item is KnowledgePageCategoryBreadcrumb['path'][number] => item !== null)
  };
}

function normalizePageDetail(value: BackendKnowledgePageDetailResponse): KnowledgePageDetail {
  const metadata = isRecord(value.metadata) ? value.metadata : {};
  const links = Array.isArray(value.links) ? value.links : [];

  return {
    id: typeof value.id === 'string' ? value.id : '',
    category_id: typeof value.category_id === 'string' ? value.category_id : null,
    title: typeof value.title === 'string' ? value.title : '',
    summary: typeof value.summary === 'string' ? value.summary : null,
    content_markdown: typeof value.content_markdown === 'string' ? value.content_markdown : '',
    created_at: maybeTimestamp(metadata.created_at) || maybeTimestamp(value.created_at),
    updated_at: maybeTimestamp(metadata.updated_at) || maybeTimestamp(value.updated_at),
    links: links.map(normalizePageLink).filter((link): link is KnowledgePageLink => link !== null),
    category_breadcrumb: normalizeCategoryBreadcrumb(value.category_breadcrumb)
  };
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
  async getCategoryTree(): Promise<KnowledgeCategoryTreeResponse> {
    const response = await apiClient<BackendKnowledgeCategoryTreeResponse>('/api/knowledge/category');
    return normalizeCategoryTreeResponse(response);
  },

  async getCategoryPages(categoryId: string): Promise<KnowledgeCategoryPagesResponse> {
    const response = await apiClient<BackendKnowledgeCategoryPagesResponse>(
      `/api/knowledge/category/${encodeURIComponent(categoryId)}/pages`
    );
    return normalizeCategoryPagesResponse(response);
  },

  async getPage(pageId: string): Promise<KnowledgePageDetail> {
    const response = await apiClient<BackendKnowledgePageDetailResponse>(`/api/knowledge/page/${encodeURIComponent(pageId)}`);
    return normalizePageDetail(response);
  },

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
