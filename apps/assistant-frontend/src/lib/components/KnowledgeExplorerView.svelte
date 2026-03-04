<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  import type { ExplorerRouteState } from '$lib/stores/workspaceViewStore';

  export let explorerRoute: ExplorerRouteState = { type: 'overview' };
  export let expandedCategories: Record<string, boolean> = {};

  const SAMPLE_CATEGORY_ID = 'knowledge-overview';
  const SAMPLE_PAGE_ID = 'knowledge-overview:getting-started';

  const dispatch = createEventDispatcher<{
    navigate: { route: ExplorerRouteState };
    expandedCategoriesChange: { expanded: Record<string, boolean> };
  }>();

  function navigate(route: ExplorerRouteState): void {
    dispatch('navigate', { route });
  }

  function toggleSampleCategory(): void {
    dispatch('expandedCategoriesChange', {
      expanded: {
        ...expandedCategories,
        [SAMPLE_CATEGORY_ID]: !expandedCategories[SAMPLE_CATEGORY_ID]
      }
    });
  }
</script>

<section class="chat-view knowledge-explorer-view" aria-label="Knowledge explorer">
  <div class="chat-meta">
    <p>Knowledge Explorer</p>
  </div>

  <div class="knowledge-content">
    <p class="knowledge-route">Current route: <strong>{explorerRoute.type}</strong></p>
    <div class="knowledge-actions">
      <button type="button" on:click={() => navigate({ type: 'overview' })}>Overview</button>
      <button type="button" on:click={() => navigate({ type: 'category', id: SAMPLE_CATEGORY_ID })}>
        Open sample category
      </button>
      <button type="button" on:click={() => navigate({ type: 'page', id: SAMPLE_PAGE_ID })}>
        Open sample page
      </button>
      <button type="button" on:click={toggleSampleCategory}>
        {expandedCategories[SAMPLE_CATEGORY_ID] ? 'Collapse sample category' : 'Expand sample category'}
      </button>
    </div>
  </div>
</section>

<style>
  .knowledge-content {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    color: var(--text);
  }

  .knowledge-route {
    color: var(--muted);
  }

  .knowledge-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .knowledge-actions button {
    border: 1px solid var(--border);
    border-radius: 0.6rem;
    background: var(--surface);
    color: var(--text);
    font: inherit;
    padding: 0.5rem 0.75rem;
    cursor: pointer;
  }
</style>
