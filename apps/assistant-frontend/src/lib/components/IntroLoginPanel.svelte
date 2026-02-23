<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let authError = '';

  const dispatch = createEventDispatcher<{ login: { email: string; password: string } }>();

  let email = '';
  let password = '';

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    dispatch('login', { email, password });
    password = '';
  }
</script>

<main class="intro-page">
  <div class="intro-content">
    <img src="/logo.png" alt="DRVID logo" class="intro-logo" />
    <h1>DRVID</h1>
    <form class="intro-login" on:submit={handleSubmit}>
      <label>
        Email
        <input type="email" bind:value={email} required autocomplete="email" />
      </label>
      <label>
        Password
        <input type="password" bind:value={password} required minlength="8" autocomplete="current-password" />
      </label>
      <button type="submit">Login</button>
    </form>
    {#if authError}
      <p class="chat-notice">{authError}</p>
    {/if}
  </div>
</main>
