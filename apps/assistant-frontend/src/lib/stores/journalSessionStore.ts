import type { CurrentUser } from '$lib/models/auth';
import type { StoredMessage } from '$lib/models/journal';

export const STORAGE_KEY = 'exobrain.assistant.session';

export interface SessionState {
  user: CurrentUser;
  journalReference: string;
  messageCount: number;
  messages: StoredMessage[];
}

/** Read a cached assistant journal state from sessionStorage. */
export function loadSessionState(): SessionState | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as SessionState;
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

/** Persist assistant journal state into sessionStorage. */
export function saveSessionState(state: SessionState): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/** Remove assistant journal state from sessionStorage. */
export function clearSessionState(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.removeItem(STORAGE_KEY);
}
