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
  let shouldScrollAfterLoading = false;

  let activeStreamingMessageId: string | null = null;
  let lastObservedScrollTop = 0;
  let isProgrammaticScroll = false;

  const autoScroller = new ChatAutoScroller();
  let catchupUntilBottom = false;
  let smoothScrollToBottomActive = false;
  let smoothScrollStartedAt = 0;
  let smoothScrollStartTop = 0;
  let smoothScrollDistance = 0;
  let frameHandle: number | null = null;
  let previousFrameTime = 0;

  $: {
    const candidateStreamingMessageId = autoScrollEnabled && streamingInProgress ? getCurrentStreamingMessageId() : null;
    if (candidateStreamingMessageId !== activeStreamingMessageId) {
      activeStreamingMessageId = candidateStreamingMessageId;
      autoScroller.maybeResume(0);

      if (activeStreamingMessageId) {
        catchupUntilBottom = true;
        startRegressiveScrollToBottom();
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

    if (loading) {
      shouldScrollAfterLoading = true;
    }

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
          startRegressiveScrollToBottom();
        } else if (switchedReference && autoScrollEnabled) {
          scrollToBottomImmediately();
        }
      }
      if (shouldScrollAfterLoading && autoScrollEnabled) {
        scrollToBottomImmediately();
        shouldScrollAfterLoading = false;
      }
      ensureAutoScrollLoop();
    }

    if (messagesContainer && !loading && shouldScrollAfterLoading && autoScrollEnabled) {
      await tick();
      scrollToBottomImmediately();
      ensureAutoScrollLoop();
      shouldScrollAfterLoading = false;
    }

    if (!loading && !autoScrollEnabled) {
      shouldScrollAfterLoading = false;
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

  function scrollToBottomImmediately(): void {
    autoScroller.maybeResume(0);
    catchupUntilBottom = false;
    smoothScrollToBottomActive = false;
    jumpToBottom('auto');
  }

  function startRegressiveScrollToBottom(): void {
    if (!messagesContainer) {
      return;
    }

    smoothScrollToBottomActive = true;
    smoothScrollStartedAt = performance.now();
    smoothScrollStartTop = messagesContainer.scrollTop;
    smoothScrollDistance = Math.max(messagesContainer.scrollHeight - messagesContainer.clientHeight - smoothScrollStartTop, 0);

    isProgrammaticScroll = true;
    messagesContainer.scrollTo({ top: smoothScrollStartTop, behavior: 'auto' });
    lastObservedScrollTop = messagesContainer.scrollTop;
    isProgrammaticScroll = false;

    if (smoothScrollDistance <= 1) {
      smoothScrollToBottomActive = false;
    }
  }

  function handleMessagesScroll(): void {
    if (!messagesContainer) {
      return;
    }

    const currentTop = messagesContainer.scrollTop;

    if (!isProgrammaticScroll && (activeStreamingMessageId || catchupUntilBottom) && currentTop < lastObservedScrollTop - 1) {
      autoScroller.markSuspended();
      catchupUntilBottom = false;
      smoothScrollToBottomActive = false;
    }

    autoScroller.maybeResume(getDistanceFromBottom(messagesContainer));
    lastObservedScrollTop = currentTop;
    ensureAutoScrollLoop();
  }

  function handleMessagesWheel(event: CustomEvent<WheelEvent>): void {
    if ((activeStreamingMessageId || catchupUntilBottom) && event.detail.deltaY < 0) {
      autoScroller.markSuspended();
      catchupUntilBottom = false;
      smoothScrollToBottomActive = false;
      ensureAutoScrollLoop();
    }
  }



  function ensureAutoScrollLoop(): void {
    if (!messagesContainer) {
      return;
    }

    const distanceFromBottom = getDistanceFromBottom(messagesContainer);
    const shouldCatchup = autoScrollEnabled && catchupUntilBottom;
    const shouldContinueSmoothScroll =
      autoScrollEnabled &&
      smoothScrollToBottomActive &&
      distanceFromBottom > 1 &&
      performance.now() - smoothScrollStartedAt < 2000;

    if (!streamingInProgress && !shouldCatchup && !shouldContinueSmoothScroll) {
      if (frameHandle != null) {
        cancelAnimationFrame(frameHandle);
        frameHandle = null;
      }
      return;
    }

    if (distanceFromBottom <= 1) {
      catchupUntilBottom = false;
      smoothScrollToBottomActive = false;
    }

    const next = autoScroller.nextPhase({
      streamingInProgress: autoScrollEnabled && streamingInProgress,
      distanceFromBottom: shouldCatchup || streamingInProgress || shouldContinueSmoothScroll ? distanceFromBottom : 0,
      forceCatchup: shouldCatchup
    });

    if (next.phase === 'idle' && !shouldContinueSmoothScroll) {
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
    const smoothElapsedMs = timestamp - smoothScrollStartedAt;
    const shouldContinueSmoothScroll =
      autoScrollEnabled && smoothScrollToBottomActive && distanceFromBottom > 1 && smoothElapsedMs < 1500;

    if (!streamingInProgress && !shouldCatchup && !shouldContinueSmoothScroll) {
      return;
    }

    if (distanceFromBottom <= 1) {
      catchupUntilBottom = false;
      smoothScrollToBottomActive = false;
      return;
    }

    const snapshot = autoScroller.nextPhase({
      streamingInProgress: autoScrollEnabled && streamingInProgress,
      distanceFromBottom,
      forceCatchup: shouldCatchup
    });

    if (snapshot.phase === 'idle' && !shouldContinueSmoothScroll) {
      return;
    }

    const currentTop = messagesContainer.scrollTop;
    const maxScrollTop = Math.max(messagesContainer.scrollHeight - messagesContainer.clientHeight, 0);
    const normalizedTime = Math.min(Math.max(smoothElapsedMs / 1500, 0), 1);
    const easeOutProgress = 2 * normalizedTime - normalizedTime * normalizedTime;
    const easedTop = smoothScrollStartTop + smoothScrollDistance * easeOutProgress;

    const scrollStep = autoScroller.getStepForPhase(snapshot.phase, deltaMs);
    const nextTop = shouldContinueSmoothScroll
      ? Math.min(easedTop, maxScrollTop)
      : Math.min(currentTop + scrollStep, maxScrollTop);

    if (nextTop > currentTop) {
      isProgrammaticScroll = true;
      messagesContainer.scrollTo({ top: nextTop, behavior: 'auto' });
      const updatedTop = messagesContainer.scrollTop;
      lastObservedScrollTop = updatedTop;
      isProgrammaticScroll = false;

      if (!streamingInProgress && updatedTop <= currentTop + 0.5) {
        catchupUntilBottom = false;
        smoothScrollToBottomActive = false;
        return;
      }
    } else if (!streamingInProgress) {
      catchupUntilBottom = false;
      smoothScrollToBottomActive = false;
      return;
    }


    if (shouldContinueSmoothScroll && normalizedTime >= 1) {
      isProgrammaticScroll = true;
      messagesContainer.scrollTo({ top: maxScrollTop, behavior: 'auto' });
      lastObservedScrollTop = messagesContainer.scrollTop;
      isProgrammaticScroll = false;
      smoothScrollToBottomActive = false;
    }

    if (!shouldContinueSmoothScroll || smoothElapsedMs >= 1500) {
      smoothScrollToBottomActive = false;
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
