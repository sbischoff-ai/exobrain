<script>
  import { fade, scale } from 'svelte/transition';
  import { onMount } from 'svelte';

  let menuOpen = false;
  let menuRoot;

  let user = null;
  let loadingUser = true;
  let email = '';
  let password = '';
  let authError = '';
  let submitting = false;

  onMount(async () => {
    await loadCurrentUser();
  });

  async function loadCurrentUser() {
    loadingUser = true;
    authError = '';
    try {
      const response = await fetch('/api/users/me');
      if (response.status === 401) {
        user = null;
        return;
      }
      if (!response.ok) {
        throw new Error(`Fetch user failed with status ${response.status}`);
      }
      user = await response.json();
    } catch (error) {
      authError = 'Could not load user details.';
      console.error(error);
    } finally {
      loadingUser = false;
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    authError = '';
    submitting = true;

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email,
          password,
          session_mode: 'web',
          issuance_policy: 'session'
        })
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      email = '';
      password = '';
      await loadCurrentUser();
    } catch (error) {
      authError = 'Login failed. Check your credentials and try again.';
      console.error(error);
    } finally {
      submitting = false;
    }
  }

  async function handleLogout() {
    authError = '';
    submitting = true;

    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST'
      });

      if (!response.ok && response.status !== 204) {
        throw new Error(`Logout failed with status ${response.status}`);
      }

      user = null;
      menuOpen = false;
    } catch (error) {
      authError = 'Logout failed. Please try again.';
      console.error(error);
    } finally {
      submitting = false;
    }
  }

  function onWindowClick(event) {
    if (!menuOpen || !menuRoot) {
      return;
    }

    if (!menuRoot.contains(event.target)) {
      menuOpen = false;
    }
  }

  function onWindowKeydown(event) {
    if (event.key === 'Escape') {
      menuOpen = false;
    }
  }
</script>

<svelte:window on:click={onWindowClick} on:keydown={onWindowKeydown} />

<div class="user-menu-root" bind:this={menuRoot}>
  <button
    class="user-trigger"
    type="button"
    on:click={() => (menuOpen = !menuOpen)}
    aria-haspopup="true"
    aria-expanded={menuOpen}
    aria-label="Open user menu"
  >
    <span class="status-dot" class:logged-in={!!user}></span>
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
      <path
        d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5z"
      />
    </svg>
  </button>

  {#if menuOpen}
    <div class="menu-panel" in:scale={{ duration: 160, start: 0.9 }} out:fade={{ duration: 120 }}>
      {#if loadingUser}
        <p class="menu-note">Loading account details...</p>
      {:else if user}
        <div class="user-details">
          <p class="label">Signed in as</p>
          <p class="name">{user.name}</p>
          <p class="email">{user.email}</p>
          <button class="action-button" type="button" on:click={handleLogout} disabled={submitting}>
            Logout
          </button>
        </div>
      {:else}
        <form class="login-form" on:submit={handleLogin}>
          <label>
            Email
            <input type="email" bind:value={email} required autocomplete="email" />
          </label>
          <label>
            Password
            <input type="password" bind:value={password} required minlength="8" autocomplete="current-password" />
          </label>
          <button class="action-button" type="submit" disabled={submitting}>Login</button>
        </form>
      {/if}

      {#if authError}
        <p class="menu-error">{authError}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .user-menu-root {
    position: relative;
  }

  .user-trigger {
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--accent-soft);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: background-color 120ms ease, border-color 120ms ease;
    position: relative;
  }

  .user-trigger:hover {
    border-color: var(--accent);
    background: #5a4f48;
  }

  .user-trigger svg {
    width: 1.45rem;
    height: 1.45rem;
    fill: currentColor;
  }

  .status-dot {
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 999px;
    background: #fb4934;
    border: 1px solid #282828;
    position: absolute;
    top: 0.16rem;
    right: 0.15rem;
  }

  .status-dot.logged-in {
    background: #b8bb26;
  }

  .menu-panel {
    position: absolute;
    right: 0;
    top: calc(100% + 0.55rem);
    width: min(18rem, 84vw);
    border-radius: 0.8rem;
    border: 1px solid var(--border);
    background: #3c3836;
    box-shadow: 0 12px 28px rgb(0 0 0 / 30%);
    padding: 0.8rem;
    z-index: 100;
  }

  .user-details,
  .login-form {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .label {
    font-size: 0.75rem;
    color: #bdae93;
  }

  .name {
    font-weight: 700;
  }

  .email {
    color: var(--muted);
    word-break: break-all;
  }

  .login-form label {
    font-size: 0.82rem;
    color: var(--muted);
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .login-form input {
    border: 1px solid var(--border);
    border-radius: 0.55rem;
    background: var(--surface);
    color: var(--text);
    font: inherit;
    padding: 0.45rem 0.55rem;
  }

  .login-form input:focus {
    outline: 2px solid rgb(215 153 33 / 35%);
    outline-offset: 1px;
  }

  .action-button {
    margin-top: 0.2rem;
    border: 1px solid var(--accent);
    border-radius: 0.55rem;
    background: var(--accent);
    color: #282828;
    font: inherit;
    font-weight: 700;
    padding: 0.45rem 0.7rem;
    cursor: pointer;
  }

  .action-button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .menu-note {
    color: var(--muted);
    font-size: 0.9rem;
  }

  .menu-error {
    color: #fb4934;
    margin-top: 0.55rem;
    font-size: 0.82rem;
  }
</style>
