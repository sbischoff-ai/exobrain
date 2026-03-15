<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';
  import StreamdownCode from 'svelte-streamdown/code';
  import StreamdownMath from 'svelte-streamdown/math';
  import StreamdownMermaid from 'svelte-streamdown/mermaid';
  import gruvboxDarkMedium from '@shikijs/themes/gruvbox-dark-medium';

  import type {
    KnowledgeCategoryPageListItem,
    KnowledgePageCategoryBreadcrumbItem,
    KnowledgePageDetail
  } from '$lib/models/knowledge';
  import { formatTimestamp } from '$lib/utils/datetime';
  import Breadcrumbs from './Breadcrumbs.svelte';
  import PageCard from './PageCard.svelte';

  export let page: KnowledgePageDetail | null = null;
  export let breadcrumbs: KnowledgePageCategoryBreadcrumbItem[] = [];
  export let loading = false;
  export let error = '';

  const dispatch = createEventDispatcher<{
    navigateOverview: void;
    navigateCategory: { categoryId: string };
    openPage: { pageId: string };
  }>();

  const streamdownTheme = {
    h1: { base: 'exo-md-heading' },
    h2: { base: 'exo-md-heading' },
    h3: { base: 'exo-md-heading' },
    h4: { base: 'exo-md-heading' },
    h5: { base: 'exo-md-heading' },
    h6: { base: 'exo-md-heading' },
    table: { base: 'exo-md-table-wrap', table: 'exo-md-table' },
    link: { base: 'exo-md-link' },
    blockquote: { base: 'exo-md-blockquote' },
    hr: { base: 'exo-md-hr' },
    th: { base: 'exo-md-th' },
    td: { base: 'exo-md-td' },
    li: { checkbox: 'exo-md-task-checkbox' },
    codespan: { base: 'exo-md-inline-code' },
    code: {
      container: 'exo-md-code-wrap',
      pre: 'exo-md-code-pre',
      base: 'exo-md-code',
      buttons: 'exo-md-control-group',
      language: 'exo-md-code-language'
    },
    components: {
      button: 'exo-md-control-button',
      popover: 'exo-md-control-popover'
    }
  };

  $: linkedPages =
    page?.links.map((link) => ({
      id: link.page_id,
      title: link.title,
      summary: link.summary
    } satisfies KnowledgeCategoryPageListItem)) ?? [];

  $: propertyEntries = Object.entries(page?.properties ?? {});
  $: contentBlocks = page?.content_blocks ?? [];
</script>

<section class="knowledge-page" aria-label="Knowledge page detail">
  <Breadcrumbs
    ancestors={breadcrumbs}
    current={page ? { id: page.id, name: page.title } : null}
    on:navigateOverview={() => dispatch('navigateOverview')}
    on:navigateCategory={(event) => dispatch('navigateCategory', event.detail)}
  />

  {#if error}
    <p class="error">{error}</p>
  {:else if loading}
    <p class="loading">Loading page…</p>
  {:else if !page}
    <p class="empty">Page not found.</p>
  {:else}
    <article class="page-body">
      <header>
        <h1>{page.title}</h1>
        <p class="meta">
          Created {formatTimestamp(page.created_at) || '—'} · Updated {formatTimestamp(page.updated_at) || '—'}
        </p>
      </header>

      {#if propertyEntries.length > 0}
        <section class="properties" aria-label="Page properties">
          <h2>Properties</h2>
          <dl>
            {#each propertyEntries as [key, value] (key)}
              <div class="property-row">
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            {/each}
          </dl>
        </section>
      {/if}

      {#if contentBlocks.length > 0}
        {#each contentBlocks as block (block.block_id)}
          <div class="assistant-markdown markdown-body content-block">
            <Streamdown
              content={block.markdown}
              theme={streamdownTheme}
              shikiTheme="gruvbox-dark-medium"
              shikiThemes={{ 'gruvbox-dark-medium': gruvboxDarkMedium }}
              components={{ code: StreamdownCode, math: StreamdownMath, mermaid: StreamdownMermaid }}
            />
          </div>
        {/each}
      {:else}
        <p class="empty">No content available for this page.</p>
      {/if}

      <section class="linked-pages" aria-label="Related pages">
        <h2>Related pages</h2>
        {#if linkedPages.length === 0}
          <p class="empty">No related pages.</p>
        {:else}
          <div class="links-grid">
            {#each linkedPages as linkedPage (linkedPage.id)}
              <PageCard page={linkedPage} on:open={(event) => dispatch('openPage', event.detail)} />
            {/each}
          </div>
        {/if}
      </section>
    </article>
  {/if}
</section>

<style>
  .knowledge-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .page-body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  h1 {
    margin: 0;
    color: var(--explorer-title-red);
    font-size: 1.4rem;
  }

  .meta {
    margin: 0.5rem 0 0;
    color: var(--explorer-meta-muted);
    font-size: 0.85rem;
  }

  .markdown-body {
    color: var(--text);
    line-height: 1.5;
  }

  .linked-pages {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  .properties {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    color: var(--explorer-meta-muted);
    font-size: 0.8rem;
    border: 1px solid var(--explorer-card-border);
    border-radius: 0.75rem;
    background: var(--explorer-page-properties-bg, var(--explorer-card-bg));
    padding: 0.9rem;
  }

  .properties dl {
    margin: 0;
    display: grid;
    gap: 0.2rem;
  }

  .property-row {
    display: grid;
    grid-template-columns: minmax(7rem, 10rem) minmax(0, 1fr);
    gap: 0.75rem;
  }

  .property-row dt,
  .property-row dd {
    margin: 0;
    font-family: var(--font-family-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
    line-height: 1.4;
    overflow-wrap: anywhere;
    word-break: break-word;
    white-space: pre-wrap;
  }

  .property-row dt {
    color: var(--explorer-meta-muted);
  }

  .property-row dd {
    color: var(--text);
    opacity: 0.8;
  }

  @media (max-width: 48rem) {
    .property-row {
      grid-template-columns: minmax(0, 1fr);
      gap: 0.1rem;
    }
  }

  h2 {
    margin: 0;
    font-size: 1rem;
  }

  .links-grid {
    display: grid;
    gap: 0.6rem;
  }

  .loading,
  .empty {
    margin: 0;
    color: var(--explorer-meta-muted);
  }

  .error {
    margin: 0;
    color: var(--explorer-error-text);
  }
</style>
