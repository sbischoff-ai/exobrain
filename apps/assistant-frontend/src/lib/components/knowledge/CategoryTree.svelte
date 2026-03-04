<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgeCategoryNode } from '$lib/models/knowledge';

  export let nodes: KnowledgeCategoryNode[] = [];
  export let expandedCategories: Record<string, boolean> = {};
  export let currentCategoryId = '';

  const dispatch = createEventDispatcher<{
    toggle: { categoryId: string; expanded: boolean };
    selectCategory: { categoryId: string };
  }>();

  function isExpanded(node: KnowledgeCategoryNode): boolean {
    if (node.children.length === 0) {
      return false;
    }

    return expandedCategories[node.id] ?? true;
  }
</script>

<ul class="category-tree">
  {#each nodes as node (node.id)}
    <li>
      <div class="category-row">
        {#if node.children.length > 0}
          <button
            type="button"
            class="toggle"
            aria-label={isExpanded(node) ? `Collapse ${node.name}` : `Expand ${node.name}`}
            on:click={() => dispatch('toggle', { categoryId: node.id, expanded: !isExpanded(node) })}
          >
            {isExpanded(node) ? '▾' : '▸'}
          </button>
        {:else}
          <span class="toggle-placeholder" aria-hidden="true"></span>
        {/if}

        <button
          type="button"
          class="category-link"
          class:active={currentCategoryId === node.id}
          on:click={() => dispatch('selectCategory', { categoryId: node.id })}
        >
          {node.name}
          <span class="count">({node.page_count})</span>
        </button>
      </div>

      {#if node.children.length > 0 && isExpanded(node)}
        <svelte:self
          nodes={node.children}
          {expandedCategories}
          {currentCategoryId}
          on:toggle
          on:selectCategory
        />
      {/if}
    </li>
  {/each}
</ul>

<style>
  .category-tree {
    list-style: none;
    margin: 0;
    padding-left: 0.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .category-row {
    display: flex;
    gap: 0.3rem;
    align-items: baseline;
  }

  .toggle,
  .toggle-placeholder {
    width: 1rem;
    flex: 0 0 1rem;
  }

  .toggle {
    border: none;
    background: none;
    color: var(--muted);
    cursor: pointer;
    padding: 0;
  }

  .category-link {
    border: none;
    background: none;
    color: var(--text);
    padding: 0;
    cursor: pointer;
    text-align: left;
    font: inherit;
  }

  .category-link.active {
    color: var(--accent-soft);
    font-weight: 600;
  }

  .category-link:hover {
    color: var(--accent);
    text-decoration: underline;
  }

  .count {
    color: var(--muted);
    font-size: 0.9em;
    margin-left: 0.25rem;
  }
</style>
