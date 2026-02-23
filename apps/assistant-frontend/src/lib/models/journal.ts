export type MessageRole = 'user' | 'assistant' | string;

export interface JournalEntry {
  id: string;
  reference: string;
  created_at?: string;
  updated_at?: string;
  last_message_at?: string | null;
  message_count: number;
  status?: string;
}

export interface JournalMessage {
  id: string;
  role: MessageRole;
  content: string | null;
  sequence?: number;
  created_at?: string;
  metadata?: Record<string, unknown> | null;
}

export interface ProcessInfo {
  id: string;
  toolCallId?: string;
  title: string;
  description: string;
  state: 'pending' | 'resolved' | 'error' | 'interrupted';
}

export interface StoredMessage {
  role: MessageRole;
  content: string;
  clientMessageId: string;
  sequence?: number;
  processInfos?: ProcessInfo[];
}
