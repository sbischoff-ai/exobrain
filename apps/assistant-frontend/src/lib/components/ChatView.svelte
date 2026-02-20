<script lang="ts">
  import { tick } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';

  import type { StoredMessage } from '$lib/models/journal';

  export let messages: StoredMessage[] = [];
  export let loading = false;
  export let reference = '';
  export let inputDisabled = false;
  export let requestError = '';
  export let onSend: (text: string) => void = () => {};

  let messageInput = '';
  let messagesContainer: HTMLDivElement | undefined;

  $: if (!loading) {
    tick().then(scrollToLatestMessage);
  }

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || inputDisabled) {
      return;
    }

    onSend(trimmed);
    messageInput = '';
  }

  function scrollToLatestMessage(): void {
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
  <div class="chat-meta">
    <p>Journal: <strong>{reference || '—'}</strong></p>
  </div>

  {#if loading}
    <div class="chat-loading" role="status" aria-live="polite">
      <span class="spinner"></span>
      <p>Loading journal...</p>
    </div>
  {:else}
    <div class="messages" bind:this={messagesContainer}>
      {#each messages as message, index (`${message.role}-${index}-${message.content}`)}
        <article class="message" class:user={message.role === 'user'}>
          {#if message.role === 'assistant'}
            <div class="assistant-markdown">
              <Streamdown content={message.content} />
            </div>
          {:else}
            <p>{message.content}</p>
          {/if}
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
    />
    <button type="submit" aria-label="Send message" disabled={inputDisabled || loading}>
      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
        <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
      </svg>
    </button>
  </form>
</section>
