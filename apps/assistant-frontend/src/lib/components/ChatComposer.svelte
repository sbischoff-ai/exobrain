<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let disabled = false;
  export let disabledReason = '';

  const dispatch = createEventDispatcher<{ send: { text: string } }>();

  let messageInput = '';
  let messageInputElement: HTMLTextAreaElement | null = null;

  $: disabledTooltip = disabled && disabledReason ? disabledReason : undefined;

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || disabled) {
      return;
    }

    dispatch('send', { text: trimmed });
    messageInput = '';
    resizeInput();
  }

  function resizeInput(): void {
    if (!messageInputElement) {
      return;
    }

    messageInputElement.style.height = 'auto';
    messageInputElement.style.height = `${messageInputElement.scrollHeight}px`;
  }

  function handleInput(): void {
    resizeInput();
  }

  function handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      const form = event.currentTarget instanceof HTMLElement ? event.currentTarget.closest('form') : null;
      form?.requestSubmit();
    }
  }
</script>

<form class="chat-input" on:submit={handleSubmit}>
  <label class="sr-only" for="message-input">Type your message</label>
  <textarea
    id="message-input"
    rows="1"
    bind:value={messageInput}
    bind:this={messageInputElement}
    placeholder="What's up?"
    autocomplete="off"
    {disabled}
    title={disabledTooltip}
    on:input={handleInput}
    on:keydown={handleKeyDown}
  ></textarea>
  <button type="submit" aria-label="Send message" {disabled} title={disabledTooltip}>
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
      <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
    </svg>
  </button>
</form>
