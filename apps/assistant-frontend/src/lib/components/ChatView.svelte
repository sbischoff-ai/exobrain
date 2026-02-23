<script lang="ts">
  import { afterUpdate, beforeUpdate, onDestroy, tick } from 'svelte';

  import type { StoredMessage } from '$lib/models/journal';
  import ChatComposer from '$lib/components/ChatComposer.svelte';
  import ChatMessages from '$lib/components/ChatMessages.svelte';
  import { ChatAutoScroller, getDistanceFromBottom } from '$lib/utils/chatAutoScroll';

  export let messages: StoredMessage[] = [];
  export let loading = false;
  export let loadingOlder = false;
  export let canLoadOlder = false;
  export let reference = '';
  export let inputDisabled = false;
  export let disabledReason = '';
  export let requestError = '';
  export let streamingInProgress = false;
  export let autoScrollEnabled = true;
  export let onSend: (text: string) => void = () => {};
  export let onLoadOlder: () => void = () => {};

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
  let lastObservedScrollTop = 0;
  let isProgrammaticScroll = false;

  const autoScroller = new ChatAutoScroller();
  let catchupUntilBottom = false;
  let frameHandle: number | null = null;
  let previousFrameTime = 0;

  $: {
    const candidateStreamingMessageId = autoScrollEnabled && streamingInProgress ? getCurrentStreamingMessageId() : null;
    if (candidateStreamingMessageId !== activeStreamingMessageId) {
      activeStreamingMessageId = candidateStreamingMessageId;
      autoScroller.maybeResume(0);

      if (activeStreamingMessageId) {
        catchupUntilBottom = true;
        jumpToBottom('smooth');
      }

      ensureAutoScrollLoop();
    }
  }

  $: {
    if (!streamingInProgress) {
      ensureAutoScrollLoop();
    }
  }

  $: {
    if (!autoScrollEnabled) {
      catchupUntilBottom = false;
      activeStreamingMessageId = null;
      if (frameHandle != null) {
        cancelAnimationFrame(frameHandle);
        frameHandle = null;
      }
    }
  }

  onDestroy(() => {
    if (frameHandle != null) {
      cancelAnimationFrame(frameHandle);
    }
  });

  beforeUpdate(() => {
    const currentFirstMessageId = messages[0]?.clientMessageId ?? null;
    const currentLastMessage = messages.at(-1);
    const nextMessageSignature = `${messages.length}|${currentFirstMessageId ?? ''}|${currentLastMessage?.clientMessageId ?? ''}|${currentLastMessage?.content ?? ''}|${currentLastMessage?.processInfos?.length ?? 0}`;

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
        const switchedReference = reference !== previousReference;

        if (shouldForceJumpToLatest && autoScrollEnabled) {
          catchupUntilBottom = true;
          jumpToBottom('smooth');
        } else if (switchedReference && autoScrollEnabled) {
          jumpToBottom('smooth');
        }
      }
      ensureAutoScrollLoop();
    }

    previousReference = reference;
    previousFirstMessageId = currentFirstMessageId;
    previousLastMessageId = currentLastMessage?.clientMessageId ?? null;
    previousMessageSignature = `${messages.length}|${currentFirstMessageId ?? ''}|${currentLastMessage?.clientMessageId ?? ''}|${currentLastMessage?.content ?? ''}|${currentLastMessage?.processInfos?.length ?? 0}`;
    previousLoading = loading;
  });

  function getCurrentStreamingMessageId(): string | null {
    const lastMessage = messages.at(-1);
    if (!lastMessage || lastMessage.role !== 'assistant') {
      return null;
    }

    return lastMessage.clientMessageId;
  }

  function jumpToBottom(behavior: ScrollBehavior): void {
    if (!messagesContainer) {
      return;
    }

    isProgrammaticScroll = true;
    messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior });
    requestAnimationFrame(() => {
      if (!messagesContainer) {
        return;
      }
      lastObservedScrollTop = messagesContainer.scrollTop;
      isProgrammaticScroll = false;
    });
  }

  function handleMessagesScroll(): void {
    if (!messagesContainer) {
      return;
    }

    const currentTop = messagesContainer.scrollTop;

    if (!isProgrammaticScroll && (activeStreamingMessageId || catchupUntilBottom) && currentTop < lastObservedScrollTop - 1) {
      autoScroller.markSuspended();
      catchupUntilBottom = false;
    }

    autoScroller.maybeResume(getDistanceFromBottom(messagesContainer));
    lastObservedScrollTop = currentTop;
    ensureAutoScrollLoop();
  }

  function handleMessagesWheel(event: CustomEvent<WheelEvent>): void {
    if ((activeStreamingMessageId || catchupUntilBottom) && event.detail.deltaY < 0) {
      autoScroller.markSuspended();
      catchupUntilBottom = false;
      ensureAutoScrollLoop();
    }
  }

  function isStreamingMessageAtTopBoundary(messageId: string): boolean {
    if (!messagesContainer) {
      return false;
    }

    const streamElement = messagesContainer.querySelector<HTMLElement>(`[data-message-id="${messageId}"]`);
    if (!streamElement) {
      return false;
    }

    const containerRect = messagesContainer.getBoundingClientRect();
    const streamRect = streamElement.getBoundingClientRect();
    const streamCoversViewportHeight = streamRect.height >= messagesContainer.clientHeight;

    return streamCoversViewportHeight && streamRect.top <= containerRect.top + 8;
  }

  function ensureAutoScrollLoop(): void {
    if (!messagesContainer) {
      return;
    }

    const distanceFromBottom = getDistanceFromBottom(messagesContainer);
    const shouldCatchup = autoScrollEnabled && catchupUntilBottom;
    if (!streamingInProgress && !shouldCatchup) {
      if (frameHandle != null) {
        cancelAnimationFrame(frameHandle);
        frameHandle = null;
      }
      return;
    }

    if (distanceFromBottom <= 1) {
      catchupUntilBottom = false;
    }

    const next = autoScroller.nextPhase({
      streamingInProgress: autoScrollEnabled && streamingInProgress,
      streamMessageTopAtOrAboveContainerTop: activeStreamingMessageId
        ? isStreamingMessageAtTopBoundary(activeStreamingMessageId)
        : false,
      distanceFromBottom: shouldCatchup || streamingInProgress ? distanceFromBottom : 0
    });

    if (next.phase === 'idle') {
      if (frameHandle != null) {
        cancelAnimationFrame(frameHandle);
        frameHandle = null;
      }
      return;
    }

    if (frameHandle == null) {
      previousFrameTime = performance.now();
      frameHandle = requestAnimationFrame(runAutoScrollFrame);
    }
  }

  function runAutoScrollFrame(timestamp: number): void {
    frameHandle = null;

    if (!messagesContainer) {
      return;
    }

    const deltaMs = Math.max(timestamp - previousFrameTime, 16);
    previousFrameTime = timestamp;

    const distanceFromBottom = getDistanceFromBottom(messagesContainer);
    const shouldCatchup = autoScrollEnabled && catchupUntilBottom;
    if (!streamingInProgress && !shouldCatchup) {
      return;
    }

    if (distanceFromBottom <= 1) {
      catchupUntilBottom = false;
      return;
    }

    const snapshot = autoScroller.nextPhase({
      streamingInProgress: autoScrollEnabled && streamingInProgress,
      streamMessageTopAtOrAboveContainerTop: activeStreamingMessageId
        ? isStreamingMessageAtTopBoundary(activeStreamingMessageId)
        : false,
      distanceFromBottom
    });

    if (snapshot.phase === 'idle') {
      return;
    }

    const currentTop = messagesContainer.scrollTop;
    const maxScrollTop = Math.max(messagesContainer.scrollHeight - messagesContainer.clientHeight, 0);
    const scrollStep = autoScroller.getStepForPhase(snapshot.phase, deltaMs);
    const nextTop = Math.min(currentTop + scrollStep, maxScrollTop);

    if (nextTop > currentTop) {
      isProgrammaticScroll = true;
      messagesContainer.scrollTo({ top: nextTop, behavior: 'auto' });
      const updatedTop = messagesContainer.scrollTop;
      lastObservedScrollTop = updatedTop;
      isProgrammaticScroll = false;

      if (!streamingInProgress && updatedTop <= currentTop + 0.5) {
        catchupUntilBottom = false;
        return;
      }
    } else if (!streamingInProgress) {
      catchupUntilBottom = false;
      return;
    }

    ensureAutoScrollLoop();
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
    <ChatMessages
      bind:containerElement={messagesContainer}
      {messages}
      {canLoadOlder}
      {loadingOlder}
      {onLoadOlder}
      on:scroll={handleMessagesScroll}
      on:wheel={handleMessagesWheel}
    />
  {/if}

  {#if requestError}
    <p class="chat-notice" role="status" aria-live="polite">{requestError}</p>
  {/if}

  <ChatComposer
    disabled={inputDisabled || loading}
    disabledReason={disabledReason}
    on:send={(event) => onSend(event.detail.text)}
  />
</section>
