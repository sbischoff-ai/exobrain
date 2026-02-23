<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let disabled = false;
  export let disabledReason = '';

  const dispatch = createEventDispatcher<{ send: { text: string } }>();

  let messageInput = '';

  $: disabledTooltip = disabled && disabledReason ? disabledReason : undefined;

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || disabled) {
      return;
    }

    dispatch('send', { text: trimmed });
    messageInput = '';
  }
</script>

<form class="chat-input" on:submit={handleSubmit}>
  <label class="sr-only" for="message-input">Type your message</label>
  <input
    id="message-input"
    type="text"
    bind:value={messageInput}
    placeholder="What's up?"
    autocomplete="off"
    {disabled}
    title={disabledTooltip}
  />
  <button type="submit" aria-label="Send message" {disabled} title={disabledTooltip}>
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
      <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
    </svg>
  </button>
</form>
