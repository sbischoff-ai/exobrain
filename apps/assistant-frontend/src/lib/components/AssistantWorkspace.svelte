<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import ChatView from '$lib/components/ChatView.svelte';
  import JournalSidebar from '$lib/components/JournalSidebar.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { CurrentUser } from '$lib/models/auth';
  import type { JournalEntry, StoredMessage } from '$lib/models/journal';

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

  const dispatch = createEventDispatcher<{
    logout: void;
    toggleSidebar: void;
    closeSidebar: void;
    selectJournal: { reference: string };
    send: { text: string };
    loadOlder: void;
    knowledgeUpdate: void;
  }>();
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
          class="knowledge-update-trigger"
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
  </main>
</div>

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }

  .knowledge-update-trigger {
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

  .knowledge-update-trigger:hover:not(:disabled) {
    border-color: var(--accent);
    background: #5a4f48;
  }

  .knowledge-update-trigger:disabled {
    color: var(--muted);
    opacity: 0.55;
    cursor: not-allowed;
  }

  .knowledge-update-trigger svg {
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
