<script>
  import { tick } from 'svelte';

  let messageInput = '';
  let messagesContainer;
  let nextMessageId = 1;

  let messages = [
    {
      id: nextMessageId++,
      role: 'assistant',
      text: 'Welcome to Exobrain.'
    }
  ];

  async function addMessagePair(text) {
    const trimmedText = text.trim();

    if (!trimmedText) {
      return;
    }

    messages = [
      ...messages,
      { id: nextMessageId++, role: 'user', text: trimmedText },
      { id: nextMessageId++, role: 'assistant', text: 'Okay, cool.' }
    ];

    messageInput = '';
    await tick();
    scrollToLatestMessage();
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

<svelte:head>
  <title>Exobrain Assistant</title>
</svelte:head>

<div class="app-shell">
  <header class="header">
    <div class="brand">
      <img src="/logo.png" alt="Exobrain logo" class="logo" />
      <h1>EXOBRAIN</h1>
    </div>
  </header>

  <main class="main-content">
    <section class="chat-view" aria-label="Chat interface">
      <div class="messages" bind:this={messagesContainer}>
        {#each messages as message (message.id)}
          <article class="message" class:user={message.role === 'user'}>
            <p>{message.text}</p>
          </article>
        {/each}
      </div>

      <form class="chat-input" on:submit={handleSubmit}>
        <label class="sr-only" for="message-input">Type your message</label>
        <input
          id="message-input"
          type="text"
          bind:value={messageInput}
          placeholder="What's up?"
          autocomplete="off"
        />
        <button type="submit" aria-label="Send message">
          <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
            <path d="M4 4h16v12H6.17L4 18.17V4zm2 2v7.34L7.34 12H18V6H6zm3 1h6v2H9V7zm0 3h4v2H9v-2z" />
          </svg>
        </button>
      </form>
    </section>
  </main>
</div>
