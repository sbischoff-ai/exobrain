<script lang="ts">
  import { afterUpdate, beforeUpdate, tick } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';

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

  let messageInput = '';
  let messagesContainer: HTMLDivElement | undefined;
  let autoScrollDisabledForCurrentStream = false;
  let streamScrollPace: 'normal' | 'slow' = 'normal';
  let trackedStreamingMessageId: string | null = null;
  let lastObservedScrollTop = 0;
  let isProgrammaticScroll = false;

  let previousReference = '';
  let previousFirstMessageId: string | null = null;


  $: disabledTooltip = inputDisabled && disabledReason ? disabledReason : undefined;
  let preserveScrollPosition = false;
  let previousScrollTop = 0;
  let previousScrollHeight = 0;

  beforeUpdate(() => {
    if (!messagesContainer || loading) {
      preserveScrollPosition = false;
      return;
    }

    const currentFirstMessageId = messages[0]?.clientMessageId ?? null;
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
    if (!messagesContainer || loading) {
      return;
    }

    const currentFirstMessageId = messages[0]?.clientMessageId ?? null;

    if (preserveScrollPosition) {
      const heightDelta = messagesContainer.scrollHeight - previousScrollHeight;
      messagesContainer.scrollTop = previousScrollTop + Math.max(heightDelta, 0);
      preserveScrollPosition = false;
    } else {
      await tick();
      scrollToLatestMessage();
    }

    previousReference = reference;
    previousFirstMessageId = currentFirstMessageId;
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
    if (!lastMessage || lastMessage.role !== 'assistant' || !lastMessage.content) {
      return null;
    }

    return lastMessage.clientMessageId;
  }

  $: {
    const currentStreamingId = getCurrentStreamingMessageId();

    if (currentStreamingId !== trackedStreamingMessageId) {
      trackedStreamingMessageId = currentStreamingId;
      autoScrollDisabledForCurrentStream = false;
      streamScrollPace = 'normal';
    }
  }

  function handleMessagesScroll(): void {
    if (!messagesContainer) {
      return;
    }

    const currentTop = messagesContainer.scrollTop;
    if (!isProgrammaticScroll && currentTop < lastObservedScrollTop) {
      autoScrollDisabledForCurrentStream = true;
    }

    lastObservedScrollTop = currentTop;
  }

  function handleMessagesWheel(event: WheelEvent): void {
    if (event.deltaY < 0) {
      autoScrollDisabledForCurrentStream = true;
    }
  }

  function applyScroll(top: number, behavior: ScrollBehavior): void {
    if (!messagesContainer) {
      return;
    }

    isProgrammaticScroll = true;
    messagesContainer.scrollTo({ top, behavior });
    lastObservedScrollTop = messagesContainer.scrollTop;

    requestAnimationFrame(() => {
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
    return streamRect.top <= containerRect.top + 12;
  }

  function scrollToLatestMessage(): void {
    if (!messagesContainer) {
      return;
    }

    const currentStreamingId = getCurrentStreamingMessageId();

    if (currentStreamingId && autoScrollDisabledForCurrentStream) {
      return;
    }

    if (currentStreamingId && shouldUseSlowStreamingPace(currentStreamingId)) {
      streamScrollPace = 'slow';
    }

    if (currentStreamingId && streamScrollPace === 'slow') {
      const nextTop = Math.min(messagesContainer.scrollTop + 20, messagesContainer.scrollHeight);
      applyScroll(nextTop, 'auto');
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

      {#each messages as message, index (`${message.role}-${index}-${message.content}`)}
        <article
          class="message"
          class:user={message.role === 'user'}
          data-message-id={message.clientMessageId}
          data-message-role={message.role}
        >
          <div class="assistant-markdown" class:user-markdown={message.role === 'user'}>
            <Streamdown content={message.content} />
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
