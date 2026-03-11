<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import ChatView from '$lib/components/ChatView.svelte';
  import JournalSidebar from '$lib/components/JournalSidebar.svelte';
  import KnowledgeExplorerView from '$lib/components/KnowledgeExplorerView.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { CurrentUser } from '$lib/models/auth';
  import type { JournalEntry, StoredMessage } from '$lib/models/journal';
  import type { ExplorerRouteState, WorkspaceMode } from '$lib/stores/workspaceViewStore';

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

  const dispatch = createEventDispatcher<{
    logout: void;
    toggleSidebar: void;
    closeSidebar: void;
    selectJournal: { reference: string };
    send: { text: string };
    loadOlder: void;
    knowledgeUpdate: void;
    toggleViewMode: void;
    explorerNavigate: { route: ExplorerRouteState };
    expandedCategoriesChange: { expanded: Record<string, boolean> };
    themeChange: { theme: string };
  }>();

  $: viewMode;
  $: explorerRoute;
  $: expandedCategories;

  $: viewModeButtonTitle = viewMode === 'chat' ? 'Switch to Knowledge Explorer' : 'Switch to Journal Chat';
  $: viewModeButtonLabel = viewMode === 'chat' ? 'Switch to Knowledge Explorer' : 'Switch to Journal Chat';
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
          on:click={() => dispatch('toggleViewMode')}
          aria-label={viewModeButtonLabel}
          title={viewModeButtonTitle}
        >
          {#if viewMode === 'chat'}
            <svg viewBox="0 0 64 64" role="img" aria-hidden="true" focusable="false">
              <path d="M31,7.663L2.516,0.067c-0.17-0.045-0.343-0.066-0.515-0.066c-0.437,0-0.866,0.142-1.22,0.413 C0.289,0.793,0,1.379,0,2v41.495l31,8.206V7.663z M24.43,40.274C24.304,40.714,23.903,41,23.469,41 c-0.092,0-0.184-0.013-0.275-0.038L8.727,36.829c-0.531-0.152-0.839-0.705-0.688-1.236c0.152-0.532,0.709-0.833,1.236-0.688 l14.467,4.133C24.273,39.19,24.581,39.743,24.43,40.274z M24.43,33.274C24.304,33.714,23.903,34,23.469,34 c-0.092,0-0.184-0.013-0.275-0.038L8.727,29.828c-0.531-0.152-0.839-0.706-0.688-1.236c0.152-0.532,0.709-0.833,1.236-0.688 l14.467,4.134C24.273,32.19,24.581,32.744,24.43,33.274z M24.43,26.274C24.304,26.714,23.903,27,23.469,27 c-0.092,0-0.184-0.013-0.275-0.038L8.727,22.828c-0.531-0.152-0.839-0.706-0.688-1.236c0.152-0.532,0.709-0.834,1.236-0.688 l14.467,4.134C24.273,25.19,24.581,25.744,24.43,26.274z M24.43,19.274C24.304,19.714,23.903,20,23.469,20 c-0.092,0-0.184-0.013-0.275-0.038L8.727,15.828c-0.531-0.152-0.839-0.706-0.688-1.236c0.152-0.532,0.709-0.833,1.236-0.688 l14.467,4.134C24.273,18.19,24.581,18.744,24.43,19.274z" />
              <path d="M63.219,0.414c-0.354-0.271-0.784-0.413-1.221-0.413c-0.172,0-0.345,0.022-0.514,0.066L33,7.663v44.038 l31-8.206V2C64,1.379,63.711,0.793,63.219,0.414z M39.424,32l14.467-4.134c0.528-0.145,1.084,0.155,1.236,0.688 c0.151,0.53-0.156,1.084-0.688,1.236l-14.467,4.134c-0.092,0.025-0.184,0.038-0.275,0.038c-0.435,0-0.835-0.286-0.961-0.726 C38.585,32.706,38.893,32.152,39.424,32z M54.742,36.829l-14.467,4.133C40.184,40.987,40.092,41,40,41 c-0.435,0-0.835-0.286-0.961-0.726c-0.151-0.531,0.156-1.084,0.688-1.236l14.467-4.133c0.528-0.145,1.084,0.155,1.236,0.688 C55.581,36.124,55.273,36.677,54.742,36.829z M54.742,22.828l-14.467,4.134C40.184,26.987,40.092,27,40,27 c-0.435,0-0.835-0.286-0.961-0.726c-0.151-0.53,0.156-1.084,0.688-1.236l14.467-4.134c0.528-0.146,1.084,0.155,1.236,0.688 C55.581,22.122,55.273,22.676,54.742,22.828z M54.742,15.828l-14.467,4.134C40.184,19.987,40.092,20,40,20 c-0.435,0-0.835-0.286-0.961-0.726c-0.151-0.53,0.156-1.084,0.688-1.236l14.467-4.134c0.528-0.145,1.084,0.155,1.236,0.688 C55.581,15.122,55.273,15.676,54.742,15.828z" />
              <polygon points="31,53.77 0,45.564 0,47.495 31,55.701" />
              <polygon points="33,55.701 64,47.495 64,45.564 33,53.77" />
              <path d="M35,58.034c0,1.657-1.343,3-3,3s-3-1.343-3-3c0-0.266,0.046-0.52,0.11-0.765L0,49.564v2.435 c0,0.906,0.609,1.699,1.484,1.933l25.873,6.899C28.089,62.685,29.887,64,32,64s3.911-1.315,4.643-3.169l25.873-6.899 C63.391,53.698,64,52.905,64,51.999v-2.435L34.89,57.27C34.954,57.515,35,57.769,35,58.034z" />
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
        <UserMenu
          {user}
          onLogout={async () => void dispatch('logout')}
          on:themeChange={(event) => dispatch('themeChange', event.detail)}
        />
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
