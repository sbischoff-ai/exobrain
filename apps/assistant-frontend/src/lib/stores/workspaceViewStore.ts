export const WORKSPACE_VIEW_STORAGE_KEY = 'exobrain.assistant.workspaceView';

export type WorkspaceMode = 'chat' | 'knowledge';

export type ExplorerRouteState =
  | { type: 'overview' }
  | { type: 'category'; id: string }
  | { type: 'page'; id: string };

export interface WorkspaceViewState {
  mode: WorkspaceMode;
  explorerRoute: ExplorerRouteState;
  expandedCategories: Record<string, boolean>;
}

const DEFAULT_WORKSPACE_VIEW_STATE: WorkspaceViewState = {
  mode: 'chat',
  explorerRoute: { type: 'overview' },
  expandedCategories: {}
};

function parseExplorerRoute(value: unknown): ExplorerRouteState | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const route = value as { type?: unknown; id?: unknown };

  if (route.type === 'overview') {
    return { type: 'overview' };
  }

  if (route.type === 'category' && typeof route.id === 'string' && route.id) {
    return { type: 'category', id: route.id };
  }

  if (route.type === 'page' && typeof route.id === 'string' && route.id) {
    return { type: 'page', id: route.id };
  }

  return null;
}

function parseExpandedCategories(value: unknown): Record<string, boolean> {
  if (!value || typeof value !== 'object') {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean')
  );
}

/** Read workspace mode + knowledge explorer view state from sessionStorage. */
export function loadWorkspaceViewState(): WorkspaceViewState {
  if (typeof window === 'undefined') {
    return DEFAULT_WORKSPACE_VIEW_STATE;
  }

  const raw = window.sessionStorage.getItem(WORKSPACE_VIEW_STORAGE_KEY);
  if (!raw) {
    return DEFAULT_WORKSPACE_VIEW_STATE;
  }

  try {
    const parsed = JSON.parse(raw) as {
      mode?: unknown;
      explorerRoute?: unknown;
      expandedCategories?: unknown;
    };

    const mode: WorkspaceMode = parsed.mode === 'knowledge' ? 'knowledge' : 'chat';
    const explorerRoute = parseExplorerRoute(parsed.explorerRoute) ?? { type: 'overview' };
    const expandedCategories = parseExpandedCategories(parsed.expandedCategories);

    return { mode, explorerRoute, expandedCategories };
  } catch {
    window.sessionStorage.removeItem(WORKSPACE_VIEW_STORAGE_KEY);
    return DEFAULT_WORKSPACE_VIEW_STATE;
  }
}

/** Persist workspace mode + knowledge explorer view state into sessionStorage. */
export function saveWorkspaceViewState(state: WorkspaceViewState): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.setItem(WORKSPACE_VIEW_STORAGE_KEY, JSON.stringify(state));
}

/** Remove workspace mode + knowledge explorer view state from sessionStorage. */
export function clearWorkspaceViewState(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.sessionStorage.removeItem(WORKSPACE_VIEW_STORAGE_KEY);
}
