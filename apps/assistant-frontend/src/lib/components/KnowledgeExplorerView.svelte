<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import CategoryOverview from '$lib/components/knowledge/CategoryOverview.svelte';
  import CategoryPage from '$lib/components/knowledge/CategoryPage.svelte';
  import KnowledgePage from '$lib/components/knowledge/KnowledgePage.svelte';
  import type {
    KnowledgeCategoryNode,
    KnowledgeCategoryPageListItem,
    KnowledgePageCategoryBreadcrumbItem,
    KnowledgePageDetail
  } from '$lib/models/knowledge';
  import { knowledgeService } from '$lib/services/knowledgeService';
  import type { ExplorerRouteState } from '$lib/stores/workspaceViewStore';


  interface CategoryOverviewPreview {
    category: KnowledgeCategoryNode;
    pages: KnowledgeCategoryPageListItem[];
  }

  const OVERVIEW_PREVIEW_LIMIT = 3;
  const LARGE_BRANCH_DESCENDANT_LIMIT = 8;

  export let explorerRoute: ExplorerRouteState = { type: 'overview' };
  export let expandedCategories: Record<string, boolean> = {};

  let loading = false;
  let requestError = '';
  let rootCategories: KnowledgeCategoryNode[] = [];
  let overviewPreviews: CategoryOverviewPreview[] = [];
  let categoryPages: KnowledgeCategoryPageListItem[] = [];
  let pageDetail: KnowledgePageDetail | null = null;
  let lastLoadedCategoryId = '';
  let lastLoadedPageId = '';

  const dispatch = createEventDispatcher<{
    navigate: { route: ExplorerRouteState };
    expandedCategoriesChange: { expanded: Record<string, boolean> };
  }>();

  $: currentCategory = explorerRoute.type === 'category' ? findCategoryById(rootCategories, explorerRoute.id) : null;
  $: categoryBreadcrumbs = currentCategory ? findCategoryBreadcrumbs(rootCategories, currentCategory.id) : [];

  onMount(async () => {
    await ensureTreeLoaded();
    await loadRouteData();
  });

  $: if (
    rootCategories.length > 0 &&
    ((explorerRoute.type === 'category' && explorerRoute.id !== lastLoadedCategoryId) ||
      (explorerRoute.type === 'page' && explorerRoute.id !== lastLoadedPageId))
  ) {
    void loadRouteData();
  }

  async function ensureTreeLoaded(): Promise<void> {
    loading = true;
    requestError = '';
    try {
      const { categories } = await knowledgeService.getCategoryTree();
      rootCategories = categories;
      maybeApplyBranchDefaults(categories);

      const previews = await Promise.all(
        categories.map(async (category) => {
          const { pages } = await knowledgeService.getCategoryPages(category.id);
          return {
            category,
            pages: pages.slice(0, OVERVIEW_PREVIEW_LIMIT)
          };
        })
      );
      overviewPreviews = previews;
    } catch {
      requestError = 'Could not load knowledge categories.';
    } finally {
      loading = false;
    }
  }

  async function loadRouteData(): Promise<void> {
    if (explorerRoute.type !== 'category') {
      categoryPages = [];
    }

    if (explorerRoute.type !== 'page') {
      pageDetail = null;
    }

    if (explorerRoute.type === 'category') {
      if (!currentCategory) {
        return;
      }

      loading = true;
      requestError = '';
      try {
        const { pages } = await knowledgeService.getCategoryPages(explorerRoute.id);
        categoryPages = pages;
        lastLoadedCategoryId = explorerRoute.id;
      } catch {
        requestError = 'Could not load category pages.';
      } finally {
        loading = false;
      }

      return;
    }

    if (explorerRoute.type !== 'page' || explorerRoute.id === lastLoadedPageId) {
      return;
    }

    loading = true;
    requestError = '';
    try {
      pageDetail = await knowledgeService.getPage(explorerRoute.id);
      lastLoadedPageId = explorerRoute.id;
    } catch {
      requestError = 'Could not load knowledge page.';
    } finally {
      loading = false;
    }
  }

  function navigate(route: ExplorerRouteState): void {
    dispatch('navigate', { route });
  }

  function updateExpanded(categoryId: string, expanded: boolean): void {
    dispatch('expandedCategoriesChange', {
      expanded: {
        ...expandedCategories,
        [categoryId]: expanded
      }
    });
  }

  function maybeApplyBranchDefaults(categories: KnowledgeCategoryNode[]): void {
    const nextExpanded = { ...expandedCategories };
    let changed = false;

    const stack: KnowledgeCategoryNode[] = [...categories];
    while (stack.length > 0) {
      const node = stack.pop();
      if (!node) {
        continue;
      }

      if (node.children.length > 0 && nextExpanded[node.id] === undefined) {
        const descendants = countDescendants(node);
        nextExpanded[node.id] = descendants <= LARGE_BRANCH_DESCENDANT_LIMIT;
        changed = true;
      }

      stack.push(...node.children);
    }

    if (changed) {
      dispatch('expandedCategoriesChange', { expanded: nextExpanded });
    }
  }

  function countDescendants(node: KnowledgeCategoryNode): number {
    return node.children.reduce((total, child) => total + 1 + countDescendants(child), 0);
  }

  function findCategoryById(nodes: KnowledgeCategoryNode[], id: string): KnowledgeCategoryNode | null {
    for (const node of nodes) {
      if (node.id === id) {
        return node;
      }

      const nested = findCategoryById(node.children, id);
      if (nested) {
        return nested;
      }
    }

    return null;
  }

  function findCategoryBreadcrumbs(nodes: KnowledgeCategoryNode[], id: string): KnowledgePageCategoryBreadcrumbItem[] {
    for (const node of nodes) {
      if (node.id === id) {
        return [];
      }

      const nested = findCategoryBreadcrumbs(node.children, id);
      if (nested.length > 0 || node.children.some((child) => child.id === id)) {
        return [{ id: node.id, name: node.name }, ...nested];
      }
    }

    return [];
  }
</script>

<section class="chat-view knowledge-explorer-view" aria-label="Knowledge explorer">
  <div class="chat-meta">
    <p>Knowledge Explorer</p>
  </div>

  <div class="knowledge-content">
    {#if explorerRoute.type !== 'page'}
      {#if requestError}
        <p class="error">{requestError}</p>
      {/if}

      {#if loading}
        <p class="loading">Loading…</p>
      {/if}
    {/if}

    {#if explorerRoute.type === 'overview'}
      <CategoryOverview
        previews={overviewPreviews}
        on:openCategory={(event) => navigate({ type: 'category', id: event.detail.categoryId })}
        on:openPage={(event) => navigate({ type: 'page', id: event.detail.pageId })}
      />
    {:else if explorerRoute.type === 'category'}
      <CategoryPage
        {rootCategories}
        currentCategory={currentCategory}
        breadcrumbs={categoryBreadcrumbs}
        pages={categoryPages}
        {expandedCategories}
        on:navigateOverview={() => navigate({ type: 'overview' })}
        on:navigateCategory={(event) => navigate({ type: 'category', id: event.detail.categoryId })}
        on:openPage={(event) => navigate({ type: 'page', id: event.detail.pageId })}
        on:toggleCategory={(event) => updateExpanded(event.detail.categoryId, event.detail.expanded)}
      />
    {:else}
      <KnowledgePage
        page={pageDetail}
        loading={loading}
        error={requestError}
        on:navigateOverview={() => navigate({ type: 'overview' })}
        on:navigateCategory={(event) => navigate({ type: 'category', id: event.detail.categoryId })}
        on:openPage={(event) => navigate({ type: 'page', id: event.detail.pageId })}
      />
    {/if}
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

  .loading {
    margin: 0;
    color: var(--muted);
  }

  .error {
    margin: 0;
    color: #d08a8a;
  }
</style>
