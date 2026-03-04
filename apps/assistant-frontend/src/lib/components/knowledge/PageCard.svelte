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
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .page-link {
    border: none;
    background: none;
    color: var(--accent-soft);
    font: inherit;
    font-weight: 600;
    text-align: left;
    padding: 0;
    cursor: pointer;
  }

  .page-link:hover {
    color: var(--accent);
    text-decoration: underline;
  }

  p {
    margin: 0;
    color: var(--muted);
  }
</style>
