<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgeCategoryPageListItem } from '$lib/models/knowledge';

  export let page: KnowledgeCategoryPageListItem;

  const dispatch = createEventDispatcher<{ open: { pageId: string } }>();
</script>

<article class="page-card">
  <h4>
    <button type="button" class="page-link" on:click={() => dispatch('open', { pageId: page.id })}>
      {page.title}
    </button>
  </h4>
  {#if page.summary}
    <p>{page.summary}</p>
  {/if}
</article>

<style>
  .page-card {
    border: 1px solid var(--explorer-card-border);
    border-radius: 0.75rem;
    background: var(--explorer-card-bg);
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    transition: background-color 150ms ease;
  }

  .page-card:hover {
    background: var(--explorer-card-hover-bg);
  }

  .page-link {
    border: none;
    background: none;
    color: var(--explorer-breadcrumb-link);
    font: inherit;
    font-weight: 600;
    text-align: left;
    padding: 0;
    cursor: pointer;
  }

  .page-link:hover {
    color: var(--explorer-breadcrumb-link-hover);
    text-decoration: underline;
  }

  p {
    margin: 0;
    color: var(--explorer-meta-muted);
  }
</style>
