<script lang="ts">
  import KnowledgeExplorerView from './KnowledgeExplorerView.svelte';
  import type { ExplorerRouteState } from '$lib/stores/workspaceViewStore';

  export let explorerRoute: ExplorerRouteState = { type: 'overview' };
  export let expandedCategories: Record<string, boolean> = {};

  let emittedRoutes: ExplorerRouteState[] = [];

  function onNavigate(event: CustomEvent<{ route: ExplorerRouteState }>): void {
    emittedRoutes = [...emittedRoutes, event.detail.route];
  }
</script>

<KnowledgeExplorerView {explorerRoute} {expandedCategories} on:navigate={onNavigate} />
<output data-testid="emitted-routes">{JSON.stringify(emittedRoutes)}</output>
