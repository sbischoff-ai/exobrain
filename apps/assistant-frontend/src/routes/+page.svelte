<script lang="ts">
  import { onMount } from 'svelte';
  import AssistantWorkspace from '$lib/components/AssistantWorkspace.svelte';
  import IntroLoginPanel from '$lib/components/IntroLoginPanel.svelte';
  import type { CurrentUser } from '$lib/models/auth';
  import type { JournalEntry, ProcessInfo, StoredMessage } from '$lib/models/journal';
  import { authService } from '$lib/services/authService';
  import { journalService } from '$lib/services/journalService';
  import {
    clearSessionState,
    loadSessionState,
    saveSessionState,
    type SessionState
  } from '$lib/stores/journalSessionStore';
  import { makeClientMessageId, toStoredMessages } from '$lib/utils/message';

  interface ChatStartResponse {
    stream_id: string;
  }

  interface ToolCallEventPayload {
    title: string;
    description: string;
  }

  interface ToolResponseEventPayload {
    message: string;
  }

  interface ErrorEventPayload {
    message: string;
  }

  interface MessageChunkPayload {
    text: string;
  }

  let initializing = true;
  let authenticated = false;
  let loadingJournal = false;
  let syncingMessages = false;
  let loadingOlderMessages = false;
  let sidebarCollapsed = true;
  let awaitingAssistant = false;

  let authError = '';
  let user: CurrentUser | null = null;

  let journalEntries: JournalEntry[] = [];
  let todayReference = '';
  let currentReference = '';
  let messages: StoredMessage[] = [];
  let requestError = '';
  let currentMessageCount = 0;

  $: canLoadOlderMessages = currentMessageCount > messages.length;
  $: isPastJournalSelected = Boolean(currentReference) && Boolean(todayReference) && currentReference !== todayReference;
  $: chatInputDisabled = loadingJournal || syncingMessages || isPastJournalSelected || awaitingAssistant;

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

  async function login(event: CustomEvent<{ email: string; password: string }>): Promise<void> {
    authError = '';

    try {
      await authService.login(event.detail.email, event.detail.password);
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
    awaitingAssistant = false;
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

  function updateStreamingMessage(
    assistantClientMessageId: string,
    accumulatedContent: string,
    processInfos: ProcessInfo[]
  ): void {
    messages = [
      ...messages.slice(0, -1),
      {
        role: 'assistant',
        content: accumulatedContent,
        clientMessageId: assistantClientMessageId,
        processInfos
      }
    ];
  }

  function resolvePendingProcessInfo(processInfos: ProcessInfo[], message: string): ProcessInfo[] {
    for (let index = processInfos.length - 1; index >= 0; index -= 1) {
      const item = processInfos[index];
      if (item.state === 'pending') {
        return processInfos.map((entry, entryIndex) =>
          entryIndex === index ? { ...entry, state: 'resolved', description: message } : entry
        );
      }
    }

    return [...processInfos, { id: makeClientMessageId(), title: 'Tool result', description: message, state: 'resolved' }];
  }

  function interruptPendingProcessInfos(processInfos: ProcessInfo[]): ProcessInfo[] {
    return processInfos.map((item) =>
      item.state === 'pending' ? { ...item, state: 'interrupted', description: 'Interrupted' } : item
    );
  }

  async function handleSend(event: CustomEvent<{ text: string }>): Promise<void> {
    requestError = '';

    if (isPastJournalSelected) {
      requestError = 'You can not chat with past journals.';
      return;
    }

    const text = event.detail.text;
    const userClientMessageId = makeClientMessageId();
    const assistantClientMessageId = makeClientMessageId();

    let accumulated = '';
    let processInfos: ProcessInfo[] = [];

    messages = [
      ...messages,
      { role: 'user', content: text, clientMessageId: userClientMessageId },
      { role: 'assistant', content: '', clientMessageId: assistantClientMessageId, processInfos }
    ];
    awaitingAssistant = true;

    try {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, client_message_id: userClientMessageId })
      });

      if (!response.ok) {
        throw new Error(`chat failed: ${response.status}`);
      }

      const { stream_id: streamId } = (await response.json()) as ChatStartResponse;
      await new Promise<void>((resolve, reject) => {
        const eventSource = new EventSource(`/api/chat/stream/${streamId}`);
        let doneReceived = false;

        eventSource.addEventListener('message_chunk', (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as MessageChunkPayload;
          accumulated += payload.text;
          updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
        });

        eventSource.addEventListener('tool_call', (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as ToolCallEventPayload;
          processInfos = [
            ...processInfos,
            {
              id: makeClientMessageId(),
              title: payload.title,
              description: payload.description,
              state: 'pending'
            }
          ];
          updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
        });

        eventSource.addEventListener('tool_response', (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as ToolResponseEventPayload;
          processInfos = resolvePendingProcessInfo(processInfos, payload.message);
          updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
        });

        eventSource.addEventListener('error', (event) => {
          const data = (event as MessageEvent).data;
          if (!data) {
            return;
          }
          const payload = JSON.parse(data) as ErrorEventPayload;
          processInfos = [
            ...processInfos,
            {
              id: makeClientMessageId(),
              title: 'Error',
              description: payload.message,
              state: 'error'
            }
          ];
          updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
        });

        eventSource.addEventListener('done', () => {
          doneReceived = true;
          eventSource.close();
          resolve();
        });

        eventSource.onerror = () => {
          if (doneReceived || eventSource.readyState === EventSource.CLOSED) {
            return;
          }
          eventSource.close();
          reject(new Error('assistant stream disconnected'));
        };
      });

      processInfos = interruptPendingProcessInfos(processInfos);
      updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);

      currentMessageCount += 2;
      saveSessionState(buildSessionState(currentReference, messages, currentMessageCount));
      await loadJournalEntries();
    } catch {
      requestError = 'Could not reach the assistant backend. Please try again.';
    } finally {
      awaitingAssistant = false;
    }
  }
</script>

<svelte:head>
  <title>DRVID Assistant</title>
</svelte:head>

{#if initializing}
  <div class="intro-page"><span class="spinner"></span></div>
{:else if !authenticated}
  <IntroLoginPanel {authError} on:login={login} />
{:else if user}
  <AssistantWorkspace
    {user}
    {journalEntries}
    {currentReference}
    {todayReference}
    {sidebarCollapsed}
    {messages}
    loading={loadingJournal || syncingMessages}
    loadingOlder={loadingOlderMessages}
    canLoadOlder={canLoadOlderMessages}
    inputDisabled={chatInputDisabled}
    disabledReason={isPastJournalSelected ? 'You can not chat with past journals.' : ''}
    {requestError}
    streamingInProgress={awaitingAssistant}
    autoScrollEnabled={!isPastJournalSelected}
    on:logout={logout}
    on:toggleSidebar={() => (sidebarCollapsed = !sidebarCollapsed)}
    on:closeSidebar={() => (sidebarCollapsed = true)}
    on:selectJournal={selectJournal}
    on:send={handleSend}
    on:loadOlder={loadOlderMessages}
  />
{/if}
