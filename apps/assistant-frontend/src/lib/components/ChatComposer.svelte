<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';

  export let disabled = false;
  export let disabledReason = '';

  const dispatch = createEventDispatcher<{ send: { text: string } }>();

  let messageInput = '';
  let messageInputElement: HTMLTextAreaElement | null = null;
  let previousDisabled = disabled;

  $: disabledTooltip = disabled && disabledReason ? disabledReason : undefined;

  $: {
    if (previousDisabled && !disabled) {
      void focusMessageInput();
    }

    previousDisabled = disabled;
  }

  async function focusMessageInput(): Promise<void> {
    await tick();

    if (disabled) {
      return;
    }

    messageInputElement?.focus();
  }

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || disabled) {
      return;
    }

    dispatch('send', { text: trimmed });
    messageInput = '';
    resetInputHeight();
  }

  function resizeInput(): void {
    if (!messageInputElement) {
      return;
    }

    messageInputElement.style.height = 'auto';
    messageInputElement.style.height = `${messageInputElement.scrollHeight}px`;
  }

  function resetInputHeight(): void {
    if (!messageInputElement) {
      return;
    }

    messageInputElement.style.height = '';
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
    <svg class="send-icon" viewBox="0 0 24 24" role="img" aria-hidden="true">
      <path d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-5.26l-3.92 3.36a1 1 0 0 1-1.65-.76V17H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 2v9h6.17a1 1 0 0 1 1 1v1.51l2.42-2.07a1 1 0 0 1 .65-.24H20V6H4z" />
    </svg>
  </button>
</form>


<style>
  .send-icon {
    width: 1.7rem;
    height: 1.7rem;
  }
</style>
