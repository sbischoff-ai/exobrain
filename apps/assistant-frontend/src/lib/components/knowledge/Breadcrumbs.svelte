<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgePageCategoryBreadcrumbItem } from '$lib/models/knowledge';

  export let ancestors: KnowledgePageCategoryBreadcrumbItem[] = [];
  export let current: KnowledgePageCategoryBreadcrumbItem | null = null;

  const dispatch = createEventDispatcher<{ navigateOverview: void; navigateCategory: { categoryId: string } }>();
</script>

<nav class="breadcrumbs" aria-label="Knowledge breadcrumbs">
  <button type="button" class="crumb" on:click={() => dispatch('navigateOverview')}>Overview</button>
  {#each ancestors as node}
    <span aria-hidden="true">/</span>
    <button type="button" class="crumb" on:click={() => dispatch('navigateCategory', { categoryId: node.id })}>
      {node.name}
    </button>
  {/each}
  {#if current}
    <span aria-hidden="true">/</span>
    <span class="crumb-current">{current.name}</span>
  {/if}
</nav>

<style>
  .breadcrumbs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    color: var(--explorer-meta-muted);
    font-size: 0.9rem;
  }

  .crumb {
    border: none;
    background: none;
    color: var(--explorer-breadcrumb-link);
    font: inherit;
    cursor: pointer;
    padding: 0;
  }

  .crumb:hover {
    color: var(--explorer-breadcrumb-link-hover);
    text-decoration: underline;
  }

  .crumb-current {
    color: var(--text);
    font-weight: 600;
  }
</style>
