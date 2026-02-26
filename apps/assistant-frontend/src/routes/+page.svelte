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
    tool_call_id: string;
    title: string;
    description: string;
  }

  interface ToolResponseEventPayload {
    tool_call_id: string;
    message: string;
  }

  interface ErrorEventPayload {
    tool_call_id?: string;
    message: string;
  }

  interface MessageChunkPayload {
    text: string;
  }

  const PENDING_STREAM_STORAGE_KEY = 'exobrain.assistant.pendingStreamId';

  let activeEventSource: EventSource | null = null;
  let activeStreamId = '';
  let activeStreamJournalReference = '';

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

    stopActiveStream(false);
    clearPendingStreamId();

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

    if (awaitingAssistant && activeStreamId) {
      savePendingStreamId(activeStreamId);
      stopActiveStream(true);
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

      if (reference === todayReference) {
        await resumePendingTodayStreamIfNeeded();
      }
    }
  }

  function loadPendingStreamId(): string {
    if (typeof window === 'undefined') {
      return '';
    }
    return window.sessionStorage.getItem(PENDING_STREAM_STORAGE_KEY) ?? '';
  }

  function savePendingStreamId(streamId: string): void {
    if (typeof window === 'undefined') {
      return;
    }
    window.sessionStorage.setItem(PENDING_STREAM_STORAGE_KEY, streamId);
  }

  function clearPendingStreamId(): void {
    if (typeof window === 'undefined') {
      return;
    }
    window.sessionStorage.removeItem(PENDING_STREAM_STORAGE_KEY);
  }

  function stopActiveStream(markInterrupted: boolean): void {
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }

    activeStreamId = '';
    activeStreamJournalReference = '';
    awaitingAssistant = false;

    if (markInterrupted) {
      const lastMessage = messages.at(-1);
      if (lastMessage?.role === 'assistant') {
        messages = [
          ...messages.slice(0, -1),
          {
            ...lastMessage,
            processInfos: interruptPendingProcessInfos(lastMessage.processInfos ?? [])
          }
        ];
      }
    }
  }

  async function consumeStream(streamId: string, assistantClientMessageId: string): Promise<void> {
    activeStreamId = streamId;
    activeStreamJournalReference = currentReference;

    let accumulated = messages.find((message) => message.clientMessageId === assistantClientMessageId)?.content ?? '';
    let processInfos =
      messages.find((message) => message.clientMessageId === assistantClientMessageId)?.processInfos?.slice() ?? [];

    await new Promise<void>((resolve, reject) => {
      const eventSource = new EventSource(`/api/chat/stream/${streamId}`);
      activeEventSource = eventSource;
      let doneReceived = false;

      eventSource.addEventListener('message_chunk', (event) => {
        if (currentReference !== activeStreamJournalReference) {
          return;
        }
        const payload = JSON.parse((event as MessageEvent).data) as MessageChunkPayload;
        accumulated += payload.text;
        updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
      });

      eventSource.addEventListener('tool_call', (event) => {
        if (currentReference !== activeStreamJournalReference) {
          return;
        }
        const payload = JSON.parse((event as MessageEvent).data) as ToolCallEventPayload;
        processInfos = [
          ...processInfos,
          {
            id: makeClientMessageId(),
            toolCallId: payload.tool_call_id,
            title: payload.title,
            description: payload.description,
            state: 'pending'
          }
        ];
        updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
      });

      eventSource.addEventListener('tool_response', (event) => {
        if (currentReference !== activeStreamJournalReference) {
          return;
        }
        const payload = JSON.parse((event as MessageEvent).data) as ToolResponseEventPayload;
        processInfos = resolvePendingProcessInfo(processInfos, payload.tool_call_id, payload.message);
        updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
      });

      eventSource.addEventListener('error', (event) => {
        const data = (event as MessageEvent).data;
        if (!data || currentReference !== activeStreamJournalReference) {
          return;
        }
        const payload = JSON.parse(data) as ErrorEventPayload;
        processInfos = [
          ...processInfos,
          {
            id: makeClientMessageId(),
            toolCallId: payload.tool_call_id,
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
        if (activeEventSource === eventSource) {
          activeEventSource = null;
        }
        resolve();
      });

      eventSource.onerror = () => {
        if (doneReceived || eventSource.readyState === EventSource.CLOSED) {
          return;
        }
        eventSource.close();
        if (activeEventSource === eventSource) {
          activeEventSource = null;
        }
        reject(new Error('assistant stream disconnected'));
      };
    });

    if (currentReference === activeStreamJournalReference) {
      processInfos = interruptPendingProcessInfos(processInfos);
      updateStreamingMessage(assistantClientMessageId, accumulated, processInfos);
    }

    clearPendingStreamId();
    activeStreamId = '';
    activeStreamJournalReference = '';
  }

  async function resumePendingTodayStreamIfNeeded(): Promise<void> {
    if (!todayReference || currentReference !== todayReference || awaitingAssistant) {
      return;
    }

    const pendingStreamId = loadPendingStreamId();
    if (!pendingStreamId) {
      return;
    }

    const resumeAssistantMessageId = makeClientMessageId();
    messages = [
      ...messages,
      {
        role: 'assistant',
        content: '',
        clientMessageId: resumeAssistantMessageId,
        createdAt: new Date().toISOString(),
        processInfos: []
      }
    ];
    awaitingAssistant = true;

    try {
      await consumeStream(pendingStreamId, resumeAssistantMessageId);
      currentMessageCount += 1;
      saveSessionState(buildSessionState(currentReference, messages, currentMessageCount));
      await loadJournalEntries();
    } catch {
      clearPendingStreamId();
      messages = messages.filter((message) => message.clientMessageId !== resumeAssistantMessageId || message.content);
    } finally {
      awaitingAssistant = false;
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
    const existingMessage = messages.at(-1);
    messages = [
      ...messages.slice(0, -1),
      {
        role: 'assistant',
        content: accumulatedContent,
        clientMessageId: assistantClientMessageId,
        createdAt: existingMessage?.createdAt ?? new Date().toISOString(),
        processInfos
      }
    ];
  }

  function resolvePendingProcessInfo(processInfos: ProcessInfo[], toolCallId: string, message: string): ProcessInfo[] {
    if (toolCallId) {
      for (let index = processInfos.length - 1; index >= 0; index -= 1) {
        const item = processInfos[index];
        if (item.state === 'pending' && item.toolCallId === toolCallId) {
          return processInfos.map((entry, entryIndex) =>
            entryIndex === index
              ? { ...entry, state: 'resolved', response: message }
              : entry
          );
        }
      }
    }

    for (let index = processInfos.length - 1; index >= 0; index -= 1) {
      const item = processInfos[index];
      if (item.state === 'pending') {
        return processInfos.map((entry, entryIndex) =>
          entryIndex === index
              ? { ...entry, state: 'resolved', response: message }
              : entry
        );
      }
    }

    return [
      ...processInfos,
      {
        id: makeClientMessageId(),
        toolCallId,
        title: 'Tool result',
        description: 'Completed',
        response: message,
        state: 'resolved'
      }
    ];
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

    const createdAt = new Date().toISOString();
    messages = [
      ...messages,
      { role: 'user', content: text, clientMessageId: userClientMessageId, createdAt },
      {
        role: 'assistant',
        content: '',
        clientMessageId: assistantClientMessageId,
        createdAt,
        processInfos: []
      }
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
      await consumeStream(streamId, assistantClientMessageId);

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
