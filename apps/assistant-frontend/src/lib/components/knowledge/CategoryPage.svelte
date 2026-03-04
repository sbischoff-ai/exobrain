<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgeCategoryNode, KnowledgeCategoryPageListItem, KnowledgePageCategoryBreadcrumbItem } from '$lib/models/knowledge';
  import Breadcrumbs from './Breadcrumbs.svelte';
  import CategoryTree from './CategoryTree.svelte';
  import PageCard from './PageCard.svelte';

  export let rootCategories: KnowledgeCategoryNode[] = [];
  export let currentCategory: KnowledgeCategoryNode | null = null;
  export let breadcrumbs: KnowledgePageCategoryBreadcrumbItem[] = [];
  export let pages: KnowledgeCategoryPageListItem[] = [];
  export let expandedCategories: Record<string, boolean> = {};

  const dispatch = createEventDispatcher<{
    navigateOverview: void;
    navigateCategory: { categoryId: string };
    openPage: { pageId: string };
    toggleCategory: { categoryId: string; expanded: boolean };
  }>();

  $: currentCrumb = currentCategory ? { id: currentCategory.id, name: currentCategory.name } : null;
</script>

<section class="category-page">
  <Breadcrumbs
    ancestors={breadcrumbs}
    current={currentCrumb}
    on:navigateOverview={() => dispatch('navigateOverview')}
    on:navigateCategory={(event) => dispatch('navigateCategory', event.detail)}
  />

  {#if rootCategories.length > 0}
    <div class="tree-wrap">
      <CategoryTree
        nodes={rootCategories}
        {expandedCategories}
        currentCategoryId={currentCategory?.id ?? ''}
        on:toggle={(event) => dispatch('toggleCategory', event.detail)}
        on:selectCategory={(event) => dispatch('navigateCategory', event.detail)}
      />
    </div>
  {/if}

  {#if currentCategory}
    <h2>
      {currentCategory.name}
      <span class="count">({currentCategory.page_count})</span>
    </h2>

    {#if pages.length === 0}
      <p class="empty">No pages in this category.</p>
    {:else}
      <div class="page-list">
        {#each pages as page (page.id)}
          <PageCard {page} on:open={(event) => dispatch('openPage', event.detail)} />
        {/each}
      </div>
    {/if}
  {:else}
    <p class="empty">Category not found.</p>
  {/if}
</section>

<style>
  .category-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .tree-wrap {
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    padding: 0.75rem;
  }

  h2 {
    margin: 0;
    font-size: 1.1rem;
  }

  .count {
    color: var(--muted);
    margin-left: 0.3rem;
    font-size: 0.9em;
  }

  .page-list {
    display: grid;
    gap: 0.6rem;
  }

  .empty {
    margin: 0;
    color: var(--muted);
  }
</style>
