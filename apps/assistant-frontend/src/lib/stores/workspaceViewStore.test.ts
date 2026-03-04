import { beforeEach, describe, expect, it } from 'vitest';
import {
  WORKSPACE_VIEW_STORAGE_KEY,
  clearWorkspaceViewState,
  loadWorkspaceViewState,
  saveWorkspaceViewState
} from './workspaceViewStore';

describe('workspaceViewStore', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('returns default state when no value is stored', () => {
    expect(loadWorkspaceViewState()).toEqual({
      mode: 'chat',
      explorerRoute: { type: 'overview' },
      expandedCategories: {}
    });
  });

  it('loads a saved workspace view state', () => {
    saveWorkspaceViewState({
      mode: 'knowledge',
      explorerRoute: { type: 'category', id: 'cat-1' },
      expandedCategories: { 'cat-1': true }
    });

    expect(loadWorkspaceViewState()).toEqual({
      mode: 'knowledge',
      explorerRoute: { type: 'category', id: 'cat-1' },
      expandedCategories: { 'cat-1': true }
    });
  });

  it('drops invalid payloads and removes malformed storage', () => {
    window.sessionStorage.setItem(WORKSPACE_VIEW_STORAGE_KEY, '{not-json');

    expect(loadWorkspaceViewState()).toEqual({
      mode: 'chat',
      explorerRoute: { type: 'overview' },
      expandedCategories: {}
    });
    expect(window.sessionStorage.getItem(WORKSPACE_VIEW_STORAGE_KEY)).toBeNull();
  });

  it('normalizes partial invalid state values', () => {
    window.sessionStorage.setItem(
      WORKSPACE_VIEW_STORAGE_KEY,
      JSON.stringify({
        mode: 'bad-mode',
        explorerRoute: { type: 'category', id: '' },
        expandedCategories: { a: true, b: 'nope' }
      })
    );

    expect(loadWorkspaceViewState()).toEqual({
      mode: 'chat',
      explorerRoute: { type: 'overview' },
      expandedCategories: { a: true }
    });
  });

  it('clears stored workspace view state', () => {
    saveWorkspaceViewState({
      mode: 'knowledge',
      explorerRoute: { type: 'page', id: 'p-9' },
      expandedCategories: { c: false }
    });

    clearWorkspaceViewState();
    expect(window.sessionStorage.getItem(WORKSPACE_VIEW_STORAGE_KEY)).toBeNull();
  });
});
