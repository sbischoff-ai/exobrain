<script>
  import { tick } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';
  import { createLogger } from '$lib/logging';

  const logger = createLogger('ChatView');

  let messageInput = '';
  let messagesContainer;
  let nextMessageId = 1;
  let isStreamingResponse = false;
  let requestError = '';

  let messages = [
    {
      id: nextMessageId++,
      role: 'assistant',
      text: 'Welcome to Exobrain.'
    }
  ];

  async function addMessagePair(text) {
    const trimmedText = text.trim();

    if (!trimmedText || isStreamingResponse) {
      logger.debug('message submit ignored', {
        hasText: Boolean(trimmedText),
        isStreamingResponse
      });
      return;
    }

    requestError = '';
    const userMessageId = nextMessageId++;
    const assistantMessageId = nextMessageId++;

    messages = [
      ...messages,
      { id: userMessageId, role: 'user', text: trimmedText },
      { id: assistantMessageId, role: 'assistant', text: '' }
    ];

    messageInput = '';
    isStreamingResponse = true;
    await tick();
    scrollToLatestMessage();

    try {
      logger.info('sending chat request', { messageLength: trimmedText.length });
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: trimmedText })
      });

      if (!response.ok) {
        logger.warn('chat request failed', { status: response.status });
        throw new Error(`Assistant backend request failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Assistant backend returned an empty response stream');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const result = await reader.read();
        done = result.done;

        if (!done) {
          const chunk = decoder.decode(result.value, { stream: true });
          messages = messages.map((message) =>
            message.id === assistantMessageId
              ? { ...message, text: `${message.text}${chunk}` }
              : message
          );
          await tick();
          scrollToLatestMessage();
        }
      }

      const trailingChunk = decoder.decode();
      if (trailingChunk) {
        messages = messages.map((message) =>
          message.id === assistantMessageId
            ? { ...message, text: `${message.text}${trailingChunk}` }
            : message
        );
      }
    } catch (error) {
      logger.error('chat request error', { error });
      requestError = 'Could not reach the assistant backend. Please try again.';
      messages = messages.map((message) =>
        message.id === assistantMessageId
          ? {
              ...message,
              text: 'Sorry, I could not generate a response because the connection failed.'
            }
          : message
      );
    } finally {
      logger.debug('chat request finished');
      isStreamingResponse = false;
      await tick();
      scrollToLatestMessage();
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    addMessagePair(messageInput);
  }

  function scrollToLatestMessage() {
    if (!messagesContainer) {
      return;
    }

    messagesContainer.scrollTo({
      top: messagesContainer.scrollHeight,
      behavior: 'smooth'
    });
  }
</script>

<section class="chat-view" aria-label="Chat interface">
  <div class="messages" bind:this={messagesContainer}>
    {#each messages as message (message.id)}
      <article class="message" class:user={message.role === 'user'}>
        {#if message.role === 'assistant'}
          <div class="assistant-markdown">
            <Streamdown content={message.text} />
          </div>
        {:else}
          <p>{message.text}</p>
        {/if}
      </article>
    {/each}
  </div>

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
      disabled={isStreamingResponse}
    />
    <button type="submit" aria-label="Send message" disabled={isStreamingResponse}>
      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
        <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
      </svg>
    </button>
  </form>
</section>
