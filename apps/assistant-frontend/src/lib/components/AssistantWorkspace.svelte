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
  export let streamingInProgress = false;
  export let autoScrollEnabled = true;

  const dispatch = createEventDispatcher<{
    logout: void;
    toggleSidebar: void;
    closeSidebar: void;
    selectJournal: { reference: string };
    send: { text: string };
    loadOlder: void;
  }>();
</script>

<div class="app-shell">
  <header class="header">
    <div class="header-inner">
      <div class="brand">
        <img src="/logo.png" alt="DRVID logo" class="logo" />
        <h1>DRVID</h1>
      </div>
      <UserMenu {user} onLogout={() => dispatch('logout')} />
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
      {streamingInProgress}
      {autoScrollEnabled}
      onSend={(text) => dispatch('send', { text })}
      onLoadOlder={() => dispatch('loadOlder')}
    />
  </main>
</div>
