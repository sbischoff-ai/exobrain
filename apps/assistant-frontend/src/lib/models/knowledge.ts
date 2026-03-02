export interface KnowledgeUpdateResponse {
  job_id: string;
  status?: string;
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
