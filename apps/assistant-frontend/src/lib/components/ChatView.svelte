<script lang="ts">
  import { afterUpdate, beforeUpdate, tick } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';
  import StreamdownCode from 'svelte-streamdown/code';

  import type { StoredMessage } from '$lib/models/journal';

  export let messages: StoredMessage[] = [];
  export let loading = false;
  export let loadingOlder = false;
  export let canLoadOlder = false;
  export let reference = '';
  export let inputDisabled = false;
  export let disabledReason = '';
  export let requestError = '';
  export let onSend: (text: string) => void = () => {};
  export let onLoadOlder: () => void = () => {};

  const streamdownTheme = {
    h1: { base: 'exo-md-heading' },
    h2: { base: 'exo-md-heading' },
    h3: { base: 'exo-md-heading' },
    h4: { base: 'exo-md-heading' },
    h5: { base: 'exo-md-heading' },
    h6: { base: 'exo-md-heading' },
    table: { base: 'exo-md-table-wrap', table: 'exo-md-table' },
    link: { base: 'exo-md-link' },
    blockquote: { base: 'exo-md-blockquote' },
    hr: { base: 'exo-md-hr' },
    th: { base: 'exo-md-th' },
    td: { base: 'exo-md-td' },
    li: { checkbox: 'exo-md-task-checkbox' },
    codespan: { base: 'exo-md-inline-code' },
    code: {
      container: 'exo-md-code-wrap',
      pre: 'exo-md-code-pre',
      base: 'exo-md-code',
      buttons: 'exo-md-control-group',
      language: 'exo-md-code-language'
    },
    components: {
      button: 'exo-md-control-button',
      popover: 'exo-md-control-popover'
    }
  };

  let messageInput = '';
  let messagesContainer: HTMLDivElement | undefined;

  let previousReference = '';
  let previousFirstMessageId: string | null = null;
  let previousLastMessageId: string | null = null;
  let previousMessageSignature = '';
  let previousLoading = false;

  let preserveScrollPosition = false;
  let previousScrollTop = 0;
  let previousScrollHeight = 0;
  let shouldReactToMessageUpdate = false;
  let shouldForceJumpToLatest = false;

  let activeStreamingMessageId: string | null = null;
  let streamScrollMode: 'normal' | 'slow' | 'paused' = 'normal';
  let lastObservedScrollTop = 0;
  let isProgrammaticScroll = false;

  $: disabledTooltip = inputDisabled && disabledReason ? disabledReason : undefined;

  $: {
    const nextStreamingMessageId = getCurrentStreamingMessageId();
    if (nextStreamingMessageId !== activeStreamingMessageId) {
      activeStreamingMessageId = nextStreamingMessageId;
      streamScrollMode = 'normal';
    }
  }

  beforeUpdate(() => {
    const currentFirstMessageId = messages[0]?.clientMessageId ?? null;
    const currentLastMessage = messages.at(-1);
    const nextMessageSignature = `${messages.length}|${currentFirstMessageId ?? ''}|${currentLastMessage?.clientMessageId ?? ''}|${currentLastMessage?.content ?? ''}`;

    shouldReactToMessageUpdate =
      previousReference !== reference ||
      previousMessageSignature !== nextMessageSignature ||
      (previousLoading && !loading);

    const currentLastMessageId = currentLastMessage?.clientMessageId ?? null;
    shouldForceJumpToLatest =
      previousLastMessageId !== null &&
      currentLastMessageId !== null &&
      currentLastMessageId !== previousLastMessageId &&
      !preserveScrollPosition;

    if (!messagesContainer || loading) {
      preserveScrollPosition = false;
      return;
    }

    const sameReference = reference === previousReference;

    const prependedOlderMessages =
      sameReference &&
      previousFirstMessageId !== null &&
      currentFirstMessageId !== null &&
      previousFirstMessageId !== currentFirstMessageId &&
      messages.some((message) => message.clientMessageId === previousFirstMessageId);

    if (!prependedOlderMessages) {
      preserveScrollPosition = false;
      return;
    }

    preserveScrollPosition = true;
    previousScrollTop = messagesContainer.scrollTop;
    previousScrollHeight = messagesContainer.scrollHeight;
  });

  afterUpdate(async () => {
    const currentFirstMessageId = messages[0]?.clientMessageId ?? null;
    const currentLastMessage = messages.at(-1);

    if (messagesContainer && !loading && shouldReactToMessageUpdate) {
      if (preserveScrollPosition) {
        const heightDelta = messagesContainer.scrollHeight - previousScrollHeight;
        messagesContainer.scrollTop = previousScrollTop + Math.max(heightDelta, 0);
        preserveScrollPosition = false;
        lastObservedScrollTop = messagesContainer.scrollTop;
      } else {
        await tick();
        scrollToLatestMessage(shouldForceJumpToLatest);
      }
    }

    previousReference = reference;
    previousFirstMessageId = currentFirstMessageId;
    previousLastMessageId = currentLastMessage?.clientMessageId ?? null;
    previousMessageSignature = `${messages.length}|${currentFirstMessageId ?? ''}|${currentLastMessage?.clientMessageId ?? ''}|${currentLastMessage?.content ?? ''}`;
    previousLoading = loading;
  });

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || inputDisabled) {
      return;
    }

    onSend(trimmed);
    messageInput = '';
  }

  function getCurrentStreamingMessageId(): string | null {
    const lastMessage = messages.at(-1);
    if (!lastMessage || lastMessage.role !== 'assistant') {
      return null;
    }

    return lastMessage.clientMessageId;
  }

  function isNearBottom(): boolean {
    if (!messagesContainer) {
      return false;
    }

    const distanceFromBottom = messagesContainer.scrollHeight - (messagesContainer.scrollTop + messagesContainer.clientHeight);
    return distanceFromBottom <= 20;
  }

  function handleMessagesScroll(): void {
    if (!messagesContainer) {
      return;
    }

    const currentTop = messagesContainer.scrollTop;

    if (!isProgrammaticScroll && activeStreamingMessageId) {
      if (currentTop < lastObservedScrollTop - 1) {
        streamScrollMode = 'paused';
      } else if (isNearBottom()) {
        streamScrollMode = 'normal';
      }
    }

    lastObservedScrollTop = currentTop;
  }

  function handleMessagesWheel(event: WheelEvent): void {
    if (activeStreamingMessageId && event.deltaY < 0) {
      streamScrollMode = 'paused';
    }
  }

  function applyScroll(top: number, behavior: ScrollBehavior): void {
    if (!messagesContainer) {
      return;
    }

    isProgrammaticScroll = true;
    messagesContainer.scrollTo({ top, behavior });

    requestAnimationFrame(() => {
      if (!messagesContainer) {
        return;
      }
      lastObservedScrollTop = messagesContainer.scrollTop;
      isProgrammaticScroll = false;
    });
  }

  function shouldUseSlowStreamingPace(streamingMessageId: string): boolean {
    if (!messagesContainer) {
      return false;
    }

    const streamElement = messagesContainer.querySelector<HTMLElement>(`[data-message-id="${streamingMessageId}"]`);
    if (!streamElement) {
      return false;
    }

    const containerRect = messagesContainer.getBoundingClientRect();
    const streamRect = streamElement.getBoundingClientRect();
    return streamRect.top <= containerRect.top + 8;
  }

  function scrollToLatestMessage(forceToLatest = false): void {
    if (!messagesContainer) {
      return;
    }

    if (forceToLatest) {
      streamScrollMode = 'normal';
      applyScroll(messagesContainer.scrollHeight, 'smooth');
      return;
    }

    if (activeStreamingMessageId) {
      if (streamScrollMode === 'paused') {
        return;
      }

      if (streamScrollMode === 'normal' && shouldUseSlowStreamingPace(activeStreamingMessageId)) {
        streamScrollMode = 'slow';
      }

      if (streamScrollMode === 'slow') {
        const maxScrollTop = Math.max(messagesContainer.scrollHeight - messagesContainer.clientHeight, 0);
        const nextTop = Math.min(messagesContainer.scrollTop + 2, maxScrollTop);
        applyScroll(nextTop, 'auto');
        return;
      }

      applyScroll(messagesContainer.scrollHeight, 'smooth');
      return;
    }

    applyScroll(messagesContainer.scrollHeight, 'smooth');
  }
</script>

<section class="chat-view" aria-label="Chat interface">
  <div class="chat-meta">
    <p>Journal: <strong>{reference || '—'}</strong></p>
  </div>

  {#if loading}
    <div class="chat-loading" role="status" aria-live="polite">
      <span class="spinner"></span>
      <p>Loading journal...</p>
    </div>
  {:else}
    <div class="messages" bind:this={messagesContainer} on:scroll={handleMessagesScroll} on:wheel={handleMessagesWheel}>
      {#if canLoadOlder}
        <div class="load-older-wrap">
          <button class="load-older" type="button" on:click={onLoadOlder} disabled={loadingOlder}>
            {#if loadingOlder}Loading older messages...{:else}Load older messages{/if}
          </button>
        </div>
      {/if}

      {#each messages as message, index (message.clientMessageId ?? `${message.role}-${index}`)}
        <article
          class="message"
          class:user={message.role === 'user'}
          data-message-id={message.clientMessageId}
          data-message-role={message.role}
        >
          <div class="assistant-markdown" class:user-markdown={message.role === 'user'}>
            <Streamdown
              content={message.content}
              theme={streamdownTheme}
              shikiTheme="gruvbox-dark-hard"
              components={{ code: StreamdownCode }}
            />
          </div>
        </article>
      {/each}
    </div>
  {/if}

  {#if requestError}
    <p class="chat-notice" role="status" aria-live="polite">{requestError}</p>
  {/if}

  <form class="chat-input" on:submit={handleSubmit}>
    <label class="sr-only" for="message-input">Type your message</label>
    <input
      id="message-input"
      type="text"
      bind:value={messageInput}
      placeholder="What's up?"
      autocomplete="off"
      disabled={inputDisabled || loading}
      title={disabledTooltip}
    />
    <button type="submit" aria-label="Send message" disabled={inputDisabled || loading} title={disabledTooltip}>
      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
        <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
      </svg>
    </button>
  </form>
</section>
