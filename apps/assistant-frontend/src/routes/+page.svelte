<script>
  import { onMount } from 'svelte';
  import ChatView from '$lib/components/ChatView.svelte';
  import JournalSidebar from '$lib/components/JournalSidebar.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import { clearSessionState, loadSessionState, saveSessionState } from '$lib/session/journalSession';

  let initializing = true;
  let authenticated = false;
  let loadingJournal = false;
  let syncingMessages = false;
  let sidebarCollapsed = true;

  let authError = '';
  let email = '';
  let password = '';
  let user = null;

  let journalEntries = [];
  let todayReference = '';
  let currentReference = '';
  let messages = [];
  let requestError = '';

  const makeClientMessageId = () =>
    globalThis?.crypto?.randomUUID?.() ?? `client-${Date.now()}-${Math.floor(Math.random() * 100000)}`;

  const toStoredMessage = (message) => ({
    role: message.role,
    content: message.content ?? '',
    clientMessageId: message.clientMessageId ?? message.client_message_id ?? message.id ?? makeClientMessageId()
  });

  const toStoredMessages = (rows) => rows.map(toStoredMessage);

  onMount(async () => {
    await bootstrap();
  });

  async function bootstrap() {
    initializing = true;
    authError = '';

    try {
      const me = await fetchCurrentUser();
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

  async function fetchCurrentUser() {
    const response = await fetch('/api/users/me');
    if (response.status === 401) {
      return null;
    }
    if (!response.ok) {
      throw new Error(`users/me failed: ${response.status}`);
    }
    return response.json();
  }

  async function login(event) {
    event.preventDefault();
    authError = '';

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          session_mode: 'web',
          issuance_policy: 'session'
        })
      });

      if (!response.ok) {
        authError = 'Login failed. Check your credentials and try again.';
        return;
      }

      email = '';
      password = '';
      authenticated = true;
      user = await fetchCurrentUser();
      await refreshAllState();
    } catch {
      authError = 'Login failed. Check your credentials and try again.';
    }
  }

  async function logout() {
    const response = await fetch('/api/auth/logout', { method: 'POST' });
    if (!response.ok && response.status !== 204) {
      throw new Error(`logout failed: ${response.status}`);
    }

    clearSessionState();
    authenticated = false;
    user = null;
    sidebarCollapsed = true;
    journalEntries = [];
    todayReference = '';
    currentReference = '';
    messages = [];
    requestError = '';
  }

  async function refreshAllState() {
    loadingJournal = true;
    try {
      await syncSessionState();
      await loadJournalEntries();
    } finally {
      loadingJournal = false;
    }
  }

  async function syncSessionState() {
    syncingMessages = true;
    try {
      const stored = loadSessionState();

      if (!stored?.journalReference) {
        const seededState = await seedTodayState();
        saveSessionState(seededState);
        applyState(seededState);
        return;
      }

      const summaryResponse = await fetch(`/api/journal/${stored.journalReference}`);
      if (summaryResponse.status === 404) {
        const seededState = await seedTodayState();
        saveSessionState(seededState);
        applyState(seededState);
        return;
      }

      const summary = await summaryResponse.json();
      let nextMessages = stored.messages || [];
      if (summary.message_count !== nextMessages.length) {
        const messagesResponse = await fetch(`/api/journal/${stored.journalReference}/messages`);
        const payload = await messagesResponse.json();
        nextMessages = toStoredMessages(payload);
      }

      const nextState = {
        user: { name: user.name, email: user.email },
        journalReference: stored.journalReference,
        messageCount: nextMessages.length,
        messages: nextMessages
      };

      saveSessionState(nextState);
      applyState(nextState);
    } finally {
      syncingMessages = false;
    }
  }

  async function seedTodayState() {
    const todayResponse = await fetch('/api/journal/today?create=true');
    const todayJournal = await todayResponse.json();
    const messageResponse = await fetch('/api/journal/today/messages');
    const payload = await messageResponse.json();
    const journalMessages = toStoredMessages(payload);

    todayReference = todayJournal.reference;
    return {
      user: { name: user.name, email: user.email },
      journalReference: todayJournal.reference,
      messageCount: journalMessages.length,
      messages: journalMessages
    };
  }

  function applyState(state) {
    currentReference = state.journalReference;
    messages = (state.messages ?? []).map(toStoredMessage);
  }

  async function loadJournalEntries() {
    const todayPayload = await fetch('/api/journal/today').then((response) => response.json());
    todayReference = todayPayload.reference;
    const listPayload = await fetch('/api/journal').then((response) => response.json());
    journalEntries = listPayload;
  }

  async function selectJournal(event) {
    const { reference } = event.detail;
    if (!reference || reference === currentReference) {
      return;
    }

    loadingJournal = true;
    try {
      const response = await fetch(`/api/journal/${reference}/messages`);
      const payload = await response.json();
      const storedMessages = toStoredMessages(payload);
      const nextState = {
        user: { name: user.name, email: user.email },
        journalReference: reference,
        messageCount: storedMessages.length,
        messages: storedMessages
      };

      saveSessionState(nextState);
      applyState(nextState);
    } finally {
      loadingJournal = false;
    }
  }

  async function handleSend(text) {
    requestError = '';

    const userClientMessageId = makeClientMessageId();
    const assistantClientMessageId = makeClientMessageId();

    const optimisticMessages = [
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

      const nextState = {
        user: { name: user.name, email: user.email },
        journalReference: currentReference,
        messageCount: messages.length,
        messages
      };
      saveSessionState(nextState);
      await loadJournalEntries();
    } catch {
      requestError = 'Could not reach the assistant backend. Please try again.';
    }
  }

  function isInputDisabled() {
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
        reference={currentReference}
        inputDisabled={isInputDisabled()}
        requestError={requestError}
        onSend={handleSend}
      />
    </main>
  </div>
{/if}
