<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgeCategoryNode, KnowledgeCategoryPageListItem } from '$lib/models/knowledge';
  import PageCard from './PageCard.svelte';

  interface CategoryOverviewPreview {
    category: KnowledgeCategoryNode;
    pages: KnowledgeCategoryPageListItem[];
  }

  export let previews: CategoryOverviewPreview[] = [];

  const dispatch = createEventDispatcher<{ openCategory: { categoryId: string }; openPage: { pageId: string } }>();
</script>

<section class="overview">
  <div class="overview-grid">
    {#each previews as preview (preview.category.id)}
      <article class="category-card">
        <h3>
          <button type="button" class="category-link" on:click={() => dispatch('openCategory', { categoryId: preview.category.id })}>
            {preview.category.name}
          </button>
          <span class="count">({preview.category.page_count})</span>
        </h3>

        {#if preview.pages.length === 0}
          <p class="empty">No pages yet.</p>
        {:else}
          <div class="preview-pages">
            {#each preview.pages as page (page.id)}
              <PageCard {page} on:open={(event) => dispatch('openPage', event.detail)} />
            {/each}
          </div>
        {/if}
      </article>
    {/each}
  </div>
</section>

<style>
  .overview-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  @media (min-width: 900px) {
    .overview-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  .category-card {
    border: 1px solid var(--explorer-card-border);
    border-radius: 0.85rem;
    background: var(--explorer-card-bg);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    transition: background-color 150ms ease;
  }

  .category-card:hover {
    background: var(--explorer-card-hover-bg);
  }

  h3 {
    margin: 0;
    font-size: 1rem;
  }

  .category-link {
    border: none;
    background: none;
    color: var(--explorer-breadcrumb-link);
    font: inherit;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    padding: 0;
  }

  .category-link:hover {
    color: var(--explorer-breadcrumb-link-hover);
    text-decoration: underline;
  }

  .count {
    color: var(--explorer-meta-muted);
    font-size: 0.9em;
    margin-left: 0.3rem;
  }

  .empty {
    margin: 0;
    color: var(--explorer-meta-muted);
  }

  .preview-pages {
    display: grid;
    gap: 0.6rem;
  }
</style>
