export interface KnowledgeUpdateResponse {
  job_id: string;
  status?: string;
}

export interface KnowledgeCategoryNode {
  id: string;
  name: string;
  page_count: number;
  children: KnowledgeCategoryNode[];
}

export interface KnowledgeCategoryTreeResponse {
  categories: KnowledgeCategoryNode[];
}

export interface KnowledgeCategoryPageListItem {
  id: string;
  title: string;
  summary: string | null;
}

export interface KnowledgeCategoryPagesResponse {
  pages: KnowledgeCategoryPageListItem[];
  total_count: number | null;
}

export interface KnowledgePageLink {
  page_id: string;
  title: string;
  summary: string | null;
}

export interface KnowledgePageCategoryBreadcrumbItem {
  id: string;
  name: string;
}

export interface KnowledgePageCategoryBreadcrumb {
  path: KnowledgePageCategoryBreadcrumbItem[];
}

export interface KnowledgePageContentBlock {
  block_id: string;
  markdown: string;
}

export interface KnowledgePagePatchContentBlock {
  block_id: string;
  markdown_content: string;
}

export interface KnowledgePagePatchRequest {
  content_blocks: KnowledgePagePatchContentBlock[];
}

export interface KnowledgePagePatchResponse {
  page_id: string;
  updated_block_ids: string[];
  updated_block_count: number;
  status: string;
}

export interface KnowledgePageDetail {
  id: string;
  category_id: string | null;
  title: string;
  summary: string | null;
  properties: Record<string, string>;
  content_blocks: KnowledgePageContentBlock[];
  created_at: string;
  updated_at: string;
  links: KnowledgePageLink[];
  category_breadcrumb: KnowledgePageCategoryBreadcrumb;
}

export interface KnowledgeUpdateStatusEvent {
  job_id: string;
  state: string;
  attempt: number;
  detail: string;
  terminal: boolean;
  emitted_at: string;
}

export interface KnowledgeUpdateDoneEvent {
  job_id: string;
  state: string;
  terminal: boolean;
}

export type KnowledgeUpdateStreamEventType = 'status' | 'done';

export type KnowledgeUpdateStreamData = KnowledgeUpdateStatusEvent | KnowledgeUpdateDoneEvent;

export type ParsedKnowledgeUpdateStreamEvent =
  | { type: 'status'; data: KnowledgeUpdateStatusEvent }
  | { type: 'done'; data: KnowledgeUpdateDoneEvent };
