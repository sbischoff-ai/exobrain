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
  let categoryPageTotalCount: number | null = null;
  let pageDetail: KnowledgePageDetail | null = null;
  let lastLoadedCategoryId = '';
  let lastLoadedPageId = '';
  let lastContextCategoryId = '';

  const dispatch = createEventDispatcher<{
    navigate: { route: ExplorerRouteState };
    expandedCategoriesChange: { expanded: Record<string, boolean> };
  }>();

  $: currentCategory = explorerRoute.type === 'category' ? findCategoryById(rootCategories, explorerRoute.id) : null;
  $: categoryBreadcrumbs = currentCategory ? findCategoryBreadcrumbs(rootCategories, currentCategory.id) : [];
  $: pageBreadcrumbs = pageDetail
    ? buildPageBreadcrumbs(pageDetail.category_breadcrumb.path, rootCategories, lastContextCategoryId)
    : [];
  $: categoryTreeNodes = currentCategory ? [currentCategory] : rootCategories;

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
          const { pages, total_count } = await knowledgeService.getCategoryPages(category.id);
          return {
            category: { ...category, page_count: total_count ?? pages.length },
            pages: pages.slice(0, OVERVIEW_PREVIEW_LIMIT)
          };
        })
      );
      overviewPreviews = previews;
      for (const preview of previews) {
        rootCategories = updateCategoryPageCount(rootCategories, preview.category.id, preview.category.page_count);
      }
    } catch {
      requestError = 'Could not load knowledge categories.';
    } finally {
      loading = false;
    }
  }

  async function loadRouteData(): Promise<void> {
    if (explorerRoute.type !== 'category') {
      categoryPages = [];
      categoryPageTotalCount = null;
    }

    if (explorerRoute.type !== 'page') {
      pageDetail = null;
    }

    if (explorerRoute.type === 'category') {
      if (!currentCategory) {
        return;
      }

      lastContextCategoryId = explorerRoute.id;

      loading = true;
      requestError = '';
      try {
        const { pages, total_count } = await knowledgeService.getCategoryPages(explorerRoute.id);
        categoryPages = pages;
        categoryPageTotalCount = total_count;
        if (total_count !== null) {
          rootCategories = updateCategoryPageCount(rootCategories, explorerRoute.id, total_count);
        }
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
    if (route.type === 'category') {
      lastContextCategoryId = route.id;
    }

    dispatch('navigate', { route });
  }

  function openPage(pageId: string, categoryId?: string): void {
    if (categoryId) {
      lastContextCategoryId = categoryId;
    }

    navigate({ type: 'page', id: pageId });
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


  function updateCategoryPageCount(nodes: KnowledgeCategoryNode[], id: string, pageCount: number): KnowledgeCategoryNode[] {
    return nodes.map((node) => {
      if (node.id === id) {
        return { ...node, page_count: pageCount };
      }

      if (node.children.length === 0) {
        return node;
      }

      return {
        ...node,
        children: updateCategoryPageCount(node.children, id, pageCount)
      };
    });
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
    const path = findCategoryPath(nodes, id);
    return path.slice(0, -1);
  }

  function findCategoryPath(nodes: KnowledgeCategoryNode[], id: string): KnowledgePageCategoryBreadcrumbItem[] {
    for (const node of nodes) {
      if (node.id === id) {
        return [{ id: node.id, name: node.name }];
      }

      const nested = findCategoryPath(node.children, id);
      if (nested.length > 0) {
        return [{ id: node.id, name: node.name }, ...nested];
      }
    }

    return [];
  }

  function buildPageBreadcrumbs(
    rawPath: KnowledgePageCategoryBreadcrumbItem[],
    nodes: KnowledgeCategoryNode[],
    contextCategoryId: string
  ): KnowledgePageCategoryBreadcrumbItem[] {
    const leaf = rawPath.at(-1);
    if (!leaf) {
      return contextCategoryId ? findCategoryPath(nodes, contextCategoryId) : [];
    }

    const fullPath = findCategoryPath(nodes, leaf.id);
    return fullPath.length > 0 ? fullPath : rawPath;
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
        on:openPage={(event) => openPage(event.detail.pageId, event.detail.categoryId)}
      />
    {:else if explorerRoute.type === 'category'}
      <CategoryPage
        rootCategories={categoryTreeNodes}
        currentCategory={
          currentCategory
            ? {
                ...currentCategory,
                page_count: categoryPageTotalCount ?? currentCategory.page_count
              }
            : null
        }
        breadcrumbs={categoryBreadcrumbs}
        pages={categoryPages}
        {expandedCategories}
        on:navigateOverview={() => navigate({ type: 'overview' })}
        on:navigateCategory={(event) => navigate({ type: 'category', id: event.detail.categoryId })}
        on:openPage={(event) => openPage(event.detail.pageId, explorerRoute.id)}
        on:toggleCategory={(event) => updateExpanded(event.detail.categoryId, event.detail.expanded)}
      />
    {:else}
      <KnowledgePage
        page={pageDetail}
        breadcrumbs={pageBreadcrumbs}
        loading={loading}
        error={requestError}
        on:navigateOverview={() => navigate({ type: 'overview' })}
        on:navigateCategory={(event) => navigate({ type: 'category', id: event.detail.categoryId })}
        on:openPage={(event) => openPage(event.detail.pageId)}
      />
    {/if}
  </div>
</section>

<style>
  .knowledge-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
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
    color: var(--explorer-error-text);
  }
</style>
