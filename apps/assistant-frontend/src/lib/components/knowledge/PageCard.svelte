<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { KnowledgeCategoryPageListItem } from '$lib/models/knowledge';

  export let page: KnowledgeCategoryPageListItem;

  const dispatch = createEventDispatcher<{ open: { pageId: string } }>();

  function openPage(): void {
    dispatch('open', { pageId: page.id });
  }

  function onCardKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPage();
    }
  }
</script>

<div class="page-card" role="button" tabindex="0" on:click={openPage} on:keydown={onCardKeydown}>
  <h4 class="page-link truncate">{page.title}</h4>
  {#if page.summary}
    <p class="summary-clamp">{page.summary}</p>
  {/if}
</div>

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
    cursor: pointer;
    min-width: 0;
  }

  .page-card:hover,
  .page-card:focus-visible {
    background: var(--explorer-card-hover-bg);
  }

  .page-card:focus-visible {
    outline: 2px solid var(--explorer-breadcrumb-link-hover);
    outline-offset: 1px;
  }

  .page-link {
    color: var(--explorer-breadcrumb-link);
    font: inherit;
    font-weight: 600;
    text-align: left;
    padding: 0;
    margin: 0;
    min-width: 0;
  }

  .page-card:hover .page-link,
  .page-card:focus-visible .page-link {
    color: var(--explorer-breadcrumb-link-hover);
    text-decoration: underline;
  }

  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .summary-clamp {
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-clamp: 2;
  }

  p {
    margin: 0;
    color: var(--explorer-meta-muted);
  }
</style>
