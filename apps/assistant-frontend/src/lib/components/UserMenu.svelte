<script lang="ts">
  import { fade, scale } from 'svelte/transition';

  import type { CurrentUser } from '$lib/models/auth';

  export let user: CurrentUser | null = null;
  export let onLogout: () => Promise<void> = async () => {};

  let menuOpen = false;
  let menuRoot: HTMLDivElement | undefined;
  let authError = '';
  let submitting = false;

  async function handleLogout() {
    authError = '';
    submitting = true;

    try {
      await onLogout();
      menuOpen = false;
    } catch {
      authError = 'Logout failed. Please try again.';
    } finally {
      submitting = false;
    }
  }

  function onWindowClick(event: MouseEvent): void {
    if (!menuOpen || !menuRoot) {
      return;
    }

    if (!menuRoot.contains(event.target as Node | null)) {
      menuOpen = false;
    }
  }

  function onWindowKeydown(event: KeyboardEvent): void {
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
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
      <path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5z" />
    </svg>
  </button>

  {#if menuOpen}
    <div class="menu-panel" in:scale={{ duration: 160, start: 0.9 }} out:fade={{ duration: 120 }}>
      <div class="user-details">
        <p class="label">Signed in as</p>
        <p class="name">{user?.name}</p>
        <p class="email">{user?.email}</p>
        <button class="action-button" type="button" on:click={handleLogout} disabled={submitting}>
          Logout
        </button>
      </div>

      {#if authError}
        <p class="menu-error">{authError}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .user-menu-root { position: relative; }
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
  }
  .user-trigger:hover { border-color: var(--accent); background: #5a4f48; }
  .user-trigger svg { width: 1.45rem; height: 1.45rem; fill: currentColor; }
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
  .user-details { display: flex; flex-direction: column; gap: 0.6rem; }
  .label { font-size: 0.75rem; color: #bdae93; }
  .name { font-weight: 700; }
  .email { color: var(--muted); word-break: break-all; }
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
  .action-button:disabled { opacity: 0.6; cursor: not-allowed; }
  .menu-error { color: #fb4934; margin-top: 0.55rem; font-size: 0.82rem; }
</style>
