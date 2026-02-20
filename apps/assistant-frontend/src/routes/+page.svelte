<script lang="ts">
  import { onMount } from 'svelte';
  import ChatView from '$lib/components/ChatView.svelte';
  import JournalSidebar from '$lib/components/JournalSidebar.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { CurrentUser } from '$lib/models/auth';
  import type { JournalEntry, StoredMessage } from '$lib/models/journal';
  import { authService } from '$lib/services/authService';
  import { journalService } from '$lib/services/journalService';
  import {
    clearSessionState,
    loadSessionState,
    saveSessionState,
    type SessionState
  } from '$lib/stores/journalSessionStore';
  import { makeClientMessageId, toStoredMessages } from '$lib/utils/message';

  let initializing = true;
  let authenticated = false;
  let loadingJournal = false;
  let syncingMessages = false;
  let loadingOlderMessages = false;
  let sidebarCollapsed = true;

  let authError = '';
  let email = '';
  let password = '';
  let user: CurrentUser | null = null;

  let journalEntries: JournalEntry[] = [];
  let todayReference = '';
  let currentReference = '';
  let messages: StoredMessage[] = [];
  let requestError = '';
  let currentMessageCount = 0;

  $: canLoadOlderMessages = currentMessageCount > messages.length;

  onMount(async () => {
    await bootstrap();
  });

  async function bootstrap(): Promise<void> {
    initializing = true;
    authError = '';

    try {
      const me = await authService.getCurrentUser();
      authenticated = Boolean(me);
      user = me;

      if (authenticated) {
        await refreshAllState();
      }
    } catch {
      authError = 'Could not load session status. Please try again.';
      authenticated = false;
      user = null;
    } finally {
      initializing = false;
    }
  }

  async function login(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    authError = '';

    try {
      await authService.login(email, password);
      email = '';
      password = '';
      authenticated = true;
      user = await authService.getCurrentUser();
      await refreshAllState();
    } catch {
      authError = 'Login failed. Check your credentials and try again.';
    }
  }

  async function logout(): Promise<void> {
    await authService.logout();

    clearSessionState();
    authenticated = false;
    user = null;
    sidebarCollapsed = true;
    journalEntries = [];
    todayReference = '';
    currentReference = '';
    messages = [];
    currentMessageCount = 0;
    requestError = '';
  }

  async function refreshAllState(): Promise<void> {
    loadingJournal = true;
    try {
      await syncSessionState();
      await loadJournalEntries();
    } finally {
      loadingJournal = false;
    }
  }

  async function syncSessionState(): Promise<void> {
    syncingMessages = true;
    try {
      const stored = loadSessionState();

      if (!stored?.journalReference) {
        const seededState = await seedTodayState();
        saveSessionState(seededState);
        applyState(seededState);
        return;
      }

      const summary = await journalService.getSummary(stored.journalReference);
      let nextMessages = stored.messages || [];
      if (summary.message_count !== stored.messageCount) {
        nextMessages = await journalService.listStoredMessages(stored.journalReference);
      }

      const nextState = buildSessionState(stored.journalReference, nextMessages, summary.message_count);
      saveSessionState(nextState);
      applyState(nextState);
    } catch {
      const seededState = await seedTodayState();
      saveSessionState(seededState);
      applyState(seededState);
    } finally {
      syncingMessages = false;
    }
  }

  async function seedTodayState(): Promise<SessionState> {
    const todayJournal = await journalService.getToday(true);
    const journalMessages = toStoredMessages(await journalService.listTodayMessages());

    todayReference = todayJournal.reference;
    return buildSessionState(todayJournal.reference, journalMessages, todayJournal.message_count);
  }

  function buildSessionState(
    journalReference: string,
    storedMessages: StoredMessage[],
    messageCount: number
  ): SessionState {
    if (!user) {
      throw new Error('expected authenticated user for session state');
    }

    return {
      user: { name: user.name, email: user.email },
      journalReference,
      messageCount,
      messages: storedMessages
    };
  }

  function applyState(state: SessionState): void {
    currentReference = state.journalReference;
    currentMessageCount = state.messageCount;
    messages = state.messages ?? [];
  }

  async function loadJournalEntries(): Promise<void> {
    const todayPayload = await journalService.getToday();
    todayReference = todayPayload.reference;
    journalEntries = await journalService.listEntries();
  }

  async function selectJournal(event: CustomEvent<{ reference: string }>): Promise<void> {
    const { reference } = event.detail;
    if (!reference || reference === currentReference) {
      return;
    }

    loadingJournal = true;
    try {
      const summary = await journalService.getSummary(reference);
      const storedMessages = await journalService.listStoredMessages(reference);
      const nextState = buildSessionState(reference, storedMessages, summary.message_count);

      saveSessionState(nextState);
      applyState(nextState);
    } finally {
      loadingJournal = false;
    }
  }

  async function loadOlderMessages(): Promise<void> {
    if (!currentReference || loadingOlderMessages || !messages.length || !canLoadOlderMessages) {
      return;
    }

    const oldestSequence = messages[0]?.sequence;
    if (oldestSequence == null) {
      return;
    }

    loadingOlderMessages = true;
    try {
      const olderMessages = await journalService.listStoredMessages(currentReference, oldestSequence);
      if (!olderMessages.length) {
        return;
      }

      messages = [...olderMessages, ...messages];
      const nextState = buildSessionState(currentReference, messages, currentMessageCount);
      saveSessionState(nextState);
    } finally {
      loadingOlderMessages = false;
    }
  }

  async function handleSend(text: string): Promise<void> {
    requestError = '';

    const userClientMessageId = makeClientMessageId();
    const assistantClientMessageId = makeClientMessageId();

    const optimisticMessages: StoredMessage[] = [
      ...messages,
      { role: 'user', content: text, clientMessageId: userClientMessageId },
      { role: 'assistant', content: '', clientMessageId: assistantClientMessageId }
    ];
    messages = optimisticMessages;

    try {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, client_message_id: userClientMessageId })
      });

      if (!response.ok || !response.body) {
        throw new Error(`chat failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let accumulated = '';

      while (!done) {
        const part = await reader.read();
        done = part.done;
        if (!done) {
          accumulated += decoder.decode(part.value, { stream: true });
          messages = [
            ...optimisticMessages.slice(0, -1),
            { role: 'assistant', content: accumulated, clientMessageId: assistantClientMessageId }
          ];
        }
      }

      const trailing = decoder.decode();
      if (trailing) {
        accumulated += trailing;
        messages = [
          ...optimisticMessages.slice(0, -1),
          { role: 'assistant', content: accumulated, clientMessageId: assistantClientMessageId }
        ];
      }

      currentMessageCount += 2;
      saveSessionState(buildSessionState(currentReference, messages, currentMessageCount));
      await loadJournalEntries();
    } catch {
      requestError = 'Could not reach the assistant backend. Please try again.';
    }
  }

  function isInputDisabled(): boolean {
    return loadingJournal || syncingMessages || currentReference !== todayReference;
  }
</script>

<svelte:head>
  <title>Exobrain Assistant</title>
</svelte:head>

{#if initializing}
  <div class="intro-page"><span class="spinner"></span></div>
{:else if !authenticated}
  <main class="intro-page">
    <div class="intro-content">
      <img src="/logo.png" alt="Exobrain logo" class="intro-logo" />
      <h1>EXOBRAIN</h1>
      <form class="intro-login" on:submit={login}>
        <label>
          Email
          <input type="email" bind:value={email} required autocomplete="email" />
        </label>
        <label>
          Password
          <input type="password" bind:value={password} required minlength="8" autocomplete="current-password" />
        </label>
        <button type="submit">Login</button>
      </form>
      {#if authError}
        <p class="chat-notice">{authError}</p>
      {/if}
    </div>
  </main>
{:else}
  <div class="app-shell">
    <header class="header">
      <div class="header-inner">
        <div class="brand">
          <img src="/logo.png" alt="Exobrain logo" class="logo" />
          <h1>EXOBRAIN</h1>
        </div>
        <UserMenu {user} onLogout={logout} />
      </div>
    </header>

    <main class="main-content workspace">
      <JournalSidebar
        entries={journalEntries}
        currentReference={currentReference}
        todayReference={todayReference}
        collapsed={sidebarCollapsed}
        on:toggle={() => (sidebarCollapsed = !sidebarCollapsed)}
        on:select={selectJournal}
      />

      <ChatView
        messages={messages}
        loading={loadingJournal || syncingMessages}
        loadingOlder={loadingOlderMessages}
        canLoadOlder={canLoadOlderMessages}
        reference={currentReference}
        inputDisabled={isInputDisabled()}
        requestError={requestError}
        onSend={handleSend}
        onLoadOlder={loadOlderMessages}
      />
    </main>
  </div>
{/if}
