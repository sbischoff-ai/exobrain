<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import ChatView from '$lib/components/ChatView.svelte';
  import JournalSidebar from '$lib/components/JournalSidebar.svelte';
  import KnowledgeExplorerView from '$lib/components/KnowledgeExplorerView.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { CurrentUser } from '$lib/models/auth';
  import type { JournalEntry, StoredMessage } from '$lib/models/journal';
  import type { ExplorerRouteState, WorkspaceMode } from '$lib/stores/workspaceViewStore';
  import type { ThemeName } from '$lib/stores/themeStore';

  export let user: CurrentUser;
  export let journalEntries: JournalEntry[] = [];
  export let currentReference = '';
  export let todayReference = '';
  export let sidebarCollapsed = true;
  export let messages: StoredMessage[] = [];
  export let loading = false;
  export let loadingOlder = false;
  export let canLoadOlder = false;
  export let inputDisabled = false;
  export let disabledReason = '';
  export let requestError = '';
  export let requestStatus = '';
  export let streamingInProgress = false;
  export let autoScrollEnabled = true;
  export let knowledgeUpdateDisabled = false;
  export let knowledgeUpdateTooltip = '';
  export let knowledgeUpdateInProgress = false;
  export let viewMode: WorkspaceMode = 'chat';
  export let explorerRoute: ExplorerRouteState = { type: 'overview' };
  export let expandedCategories: Record<string, boolean> = {};
  export let theme: ThemeName = 'gruvbox-dark';

  const dispatch = createEventDispatcher<{
    logout: void;
    toggleSidebar: void;
    closeSidebar: void;
    selectJournal: { reference: string };
    send: { text: string };
    loadOlder: void;
    knowledgeUpdate: void;
    toggleViewMode: void;
    toggleTheme: void;
    explorerNavigate: { route: ExplorerRouteState };
    expandedCategoriesChange: { expanded: Record<string, boolean> };
  }>();

  $: viewMode;
  $: explorerRoute;
  $: expandedCategories;

  $: viewModeButtonTitle = viewMode === 'chat' ? 'Switch to Knowledge Explorer' : 'Switch to Journal Chat';
  $: viewModeButtonLabel = viewMode === 'chat' ? 'Switch to Knowledge Explorer' : 'Switch to Journal Chat';
  $: themeButtonTitle =
    theme === 'gruvbox-dark' ? 'Switch to purple-intelligence theme' : 'Switch to gruvbox-dark theme';
  $: themeButtonLabel = themeButtonTitle;
</script>

<div class="app-shell">
  <header class="header">
    <div class="header-inner">
      <div class="brand">
        <img src="/logo.png" alt="DRVID logo" class="logo" />
        <h1>DRVID</h1>
      </div>
      <div class="header-actions">
        <button
          class="header-action-button"
          type="button"
          on:click={() => dispatch('toggleTheme')}
          aria-label={themeButtonLabel}
          title={themeButtonTitle}
        >
          <span aria-hidden="true">◐</span>
        </button>
        <button
          class="header-action-button"
          type="button"
          on:click={() => dispatch('toggleViewMode')}
          aria-label={viewModeButtonLabel}
          title={viewModeButtonTitle}
        >
          {#if viewMode === 'chat'}
            <svg viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
              <path
                d="M6 3a3 3 0 0 0-3 3v12.5A2.5 2.5 0 0 0 5.5 21H19a1 1 0 1 0 0-2H5.5a.5.5 0 0 1-.5-.5V6a1 1 0 0 1 1-1h5v10.75c0 .71.78 1.15 1.39.79L15 15.2l2.61 1.34a.9.9 0 0 0 1.39-.79V5h1a1 1 0 0 1 1 1v4a1 1 0 1 0 2 0V6a3 3 0 0 0-3-3H6zm7 2h4v9.12l-1.55-.79a1 1 0 0 0-.9 0L13 14.12V5z"
              />
            </svg>
          {:else}
            <svg viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
              <path
                d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-5.26l-3.92 3.36a1 1 0 0 1-1.65-.76V17H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 2v9h6.17a1 1 0 0 1 1 1v1.51l2.42-2.07a1 1 0 0 1 .65-.24H20V6H4z"
              />
            </svg>
          {/if}
        </button>
        <button
          class="header-action-button knowledge-update-trigger"
          type="button"
          on:click={() => dispatch('knowledgeUpdate')}
          aria-label="Update knowledge base"
          title={knowledgeUpdateTooltip}
          disabled={knowledgeUpdateDisabled}
        >
          <svg
            class:spinning={knowledgeUpdateInProgress}
            viewBox="0 0 24 24"
            role="img"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M12 4a8 8 0 0 1 6.93 4H16a1 1 0 1 0 0 2h5a1 1 0 0 0 1-1V4a1 1 0 1 0-2 0v2.08A10 10 0 1 0 22 12a1 1 0 1 0-2 0 8 8 0 1 1-8-8z"
            />
          </svg>
        </button>
        <UserMenu {user} onLogout={async () => void dispatch('logout')} />
      </div>
    </div>
  </header>

  <main class="main-content workspace">
    {#if viewMode === 'chat'}
      <JournalSidebar
        entries={journalEntries}
        {currentReference}
        {todayReference}
        collapsed={sidebarCollapsed}
        on:toggle={() => dispatch('toggleSidebar')}
        on:close={() => dispatch('closeSidebar')}
        on:select={(event) => dispatch('selectJournal', event.detail)}
      />

      <ChatView
        {messages}
        {loading}
        {loadingOlder}
        {canLoadOlder}
        reference={currentReference}
        {inputDisabled}
        {disabledReason}
        {requestError}
        {requestStatus}
        {streamingInProgress}
        {autoScrollEnabled}
        onSend={(text) => dispatch('send', { text })}
        onLoadOlder={() => dispatch('loadOlder')}
      />
    {:else}
      <KnowledgeExplorerView
        {explorerRoute}
        {expandedCategories}
        on:navigate={(event) => dispatch('explorerNavigate', event.detail)}
        on:expandedCategoriesChange={(event) => dispatch('expandedCategoriesChange', event.detail)}
      />
    {/if}
  </main>
</div>

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }

  .header-action-button {
    width: calc(2.75rem * var(--mobile-ui-scale, 1));
    height: calc(2.75rem * var(--mobile-ui-scale, 1));
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--accent-soft);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease, opacity 120ms ease;
  }

  .header-action-button:hover:not(:disabled) {
    border-color: var(--accent);
    background: var(--explorer-card-hover-bg);
  }

  .header-action-button:disabled {
    color: var(--muted);
    opacity: 0.55;
    cursor: not-allowed;
  }

  .header-action-button svg {
    width: calc(1.3rem * var(--mobile-ui-scale, 1));
    height: calc(1.3rem * var(--mobile-ui-scale, 1));
    fill: currentColor;
  }

  .knowledge-update-trigger svg.spinning {
    animation: knowledge-update-spin 1s linear infinite;
  }

  @keyframes knowledge-update-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
