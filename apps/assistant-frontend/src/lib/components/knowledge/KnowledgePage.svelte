<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type {
    KnowledgeCategoryPageListItem,
    KnowledgePageCategoryBreadcrumbItem,
    KnowledgePageContentBlock,
    KnowledgePageDetail
  } from '$lib/models/knowledge';
  import { knowledgeService } from '$lib/services/knowledgeService';
  import { formatTimestamp } from '$lib/utils/datetime';
  import Breadcrumbs from './Breadcrumbs.svelte';
  import PageCard from './PageCard.svelte';
  import KnowledgeContentBlock from './KnowledgeContentBlock.svelte';

  export let page: KnowledgePageDetail | null = null;
  export let breadcrumbs: KnowledgePageCategoryBreadcrumbItem[] = [];
  export let loading = false;
  export let error = '';

  const dispatch = createEventDispatcher<{
    navigateOverview: void;
    navigateCategory: { categoryId: string };
    openPage: { pageId: string };
  }>();

  let localPage: KnowledgePageDetail | null = null;
  let lastLoadedPage: KnowledgePageDetail | null = null;
  let savingBlockIds = new Set<string>();
  let saveStatusMessage = '';
  let saveStatusTone: 'success' | 'error' | '' = '';

  $: if (page !== lastLoadedPage) {
    lastLoadedPage = page;
    localPage = page
      ? {
          ...page,
          content_blocks: page.content_blocks.map((block) => ({ ...block }))
        }
      : null;
    savingBlockIds = new Set();
    saveStatusMessage = '';
    saveStatusTone = '';
  }

  $: linkedPages =
    localPage?.links.map((link) => ({
      id: link.page_id,
      title: link.title,
      summary: link.summary
    } satisfies KnowledgeCategoryPageListItem)) ?? [];

  $: propertyEntries = Object.entries(localPage?.properties ?? {});
  $: contentBlocks = localPage?.content_blocks ?? [];

  function setSaving(blockId: string, isSaving: boolean): void {
    if (isSaving) {
      savingBlockIds = new Set([...savingBlockIds, blockId]);
      return;
    }

    const next = new Set(savingBlockIds);
    next.delete(blockId);
    savingBlockIds = next;
  }

  async function handleSaveRequested(event: CustomEvent<{ blockId: string; markdownContent: string }>): Promise<void> {
    if (!localPage) {
      return;
    }

    const { blockId, markdownContent } = event.detail;

    if (savingBlockIds.has(blockId)) {
      return;
    }

    const existingBlock = localPage.content_blocks.find((block) => block.block_id === blockId);
    if (!existingBlock) {
      saveStatusTone = 'error';
      saveStatusMessage = 'Could not save: content block is no longer available.';
      return;
    }

    setSaving(blockId, true);

    try {
      await knowledgeService.patchPageContentBlocks(localPage.id, [
        {
          block_id: blockId,
          markdown_content: markdownContent
        }
      ]);

      localPage = {
        ...localPage,
        content_blocks: localPage.content_blocks.map((block: KnowledgePageContentBlock) =>
          block.block_id === blockId ? { ...block, markdown: markdownContent } : block
        )
      };
      saveStatusTone = 'success';
      saveStatusMessage = 'Block content saved successfully.';
    } catch {
      localPage = {
        ...localPage,
        content_blocks: localPage.content_blocks.map((block: KnowledgePageContentBlock) =>
          block.block_id === blockId ? { ...block, markdown: existingBlock.markdown } : block
        )
      };
      saveStatusTone = 'error';
      saveStatusMessage = 'Could not save block content. Your last saved content was restored.';
    } finally {
      setSaving(blockId, false);
    }
  }
</script>

<section class="knowledge-page" aria-label="Knowledge page detail">
  <Breadcrumbs
    ancestors={breadcrumbs}
    current={localPage ? { id: localPage.id, name: localPage.title } : null}
    on:navigateOverview={() => dispatch('navigateOverview')}
    on:navigateCategory={(event) => dispatch('navigateCategory', event.detail)}
  />

  {#if error}
    <p class="error">{error}</p>
  {:else if loading}
    <p class="loading">Loading page…</p>
  {:else if !localPage}
    <p class="empty">Page not found.</p>
  {:else}
    <article class="page-body">
      <header>
        <h1>{localPage.title}</h1>
        <p class="meta">
          Created {formatTimestamp(localPage.created_at) || '—'} · Updated {formatTimestamp(localPage.updated_at) || '—'}
        </p>
      </header>

      {#if saveStatusMessage}
        <p class="save-status" data-tone={saveStatusTone} role="status" aria-live="polite">{saveStatusMessage}</p>
      {/if}

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
          <KnowledgeContentBlock
            blockId={block.block_id}
            markdown={block.markdown}
            isSaving={savingBlockIds.has(block.block_id)}
            on:saveRequested={handleSaveRequested}
          />
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

  .save-status {
    margin: 0;
    font-size: 0.9rem;
    color: var(--explorer-meta-muted);
  }

  .save-status[data-tone='success'] {
    color: var(--explorer-success-text, var(--explorer-meta-muted));
  }

  .save-status[data-tone='error'] {
    color: var(--explorer-error-text);
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
