<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';

  import type { CurrentUser, UserConfigItem } from '$lib/models/auth';
  import { userConfigService } from '$lib/services/userConfigService';

  export let user: CurrentUser | null = null;
  export let onLogout: () => Promise<void> = async () => {};

  let menuOpen = false;
  let menuRoot: HTMLDivElement | undefined;
  let authError = '';
  let configError = '';
  let submitting = false;
  let loadingConfigs = false;
  let savingConfigs = false;
  let configs: UserConfigItem[] = [];
  let configValues: Record<string, boolean | string> = {};
  let persistedConfigValues: Record<string, boolean | string> = {};

  const dispatch = createEventDispatcher<{
    themeChange: { theme: string };
  }>();

  $: hasConfigChanges = configs.some((config) => configValues[config.key] !== persistedConfigValues[config.key]);

  async function toggleMenu(): Promise<void> {
    if (menuOpen) {
      closeMenu();
    } else {
      menuOpen = true;
      await loadConfigs();
    }
  }

  function closeMenu(): void {
    menuOpen = false;
    configError = '';

    if (!hasConfigChanges) {
      return;
    }

    configValues = { ...persistedConfigValues };
    const persistedTheme = persistedConfigValues['frontend.theme'];
    if (typeof persistedTheme === 'string') {
      dispatch('themeChange', { theme: persistedTheme });
    }
  }

  async function loadConfigs(): Promise<void> {
    if (loadingConfigs) {
      return;
    }

    loadingConfigs = true;
    configError = '';
    try {
      configs = await userConfigService.list();
      configValues = Object.fromEntries(configs.map((config) => [config.key, config.value]));
      persistedConfigValues = { ...configValues };
    } catch {
      configError = 'Could not load user configs.';
    } finally {
      loadingConfigs = false;
    }
  }

  async function saveConfigs(): Promise<void> {
    if (!configs.length) {
      return;
    }

    savingConfigs = true;
    configError = '';
    try {
      configs = await userConfigService.save(
        configs.map((config) => ({
          key: config.key,
          value: configValues[config.key]
        }))
      );
      configValues = Object.fromEntries(configs.map((config) => [config.key, config.value]));
      persistedConfigValues = { ...configValues };
    } catch {
      configError = 'Could not save user configs.';
    } finally {
      savingConfigs = false;
    }
  }

  async function handleLogout() {
    authError = '';
    submitting = true;

    try {
      await onLogout();
      closeMenu();
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
      closeMenu();
    }
  }

  function onWindowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      closeMenu();
    }
  }

  function updateConfigValue(configKey: string, value: boolean | string): void {
    configValues = { ...configValues, [configKey]: value };
    if (configKey === 'frontend.theme' && typeof value === 'string') {
      dispatch('themeChange', { theme: value });
    }
  }
</script>

<svelte:window on:click={onWindowClick} on:keydown={onWindowKeydown} />

<div class="user-menu-root" bind:this={menuRoot}>
  <button
    class="user-trigger"
    type="button"
    on:click={toggleMenu}
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

        <section class="configs" aria-label="User configs">
          <p class="label">User configs</p>
          {#if loadingConfigs}
            <p class="config-note">Loading configs…</p>
          {:else}
            {#each configs as config (config.key)}
              <div class="config-item">
                <label for={config.key} title={config.description}>{config.name}</label>
                {#if config.config_type === 'choice'}
                  <select
                    id={config.key}
                    value={String(configValues[config.key] ?? '')}
                    title={config.description}
                    on:change={(event) => updateConfigValue(config.key, (event.currentTarget as HTMLSelectElement).value)}
                  >
                    {#each config.options as option}
                      <option value={option.value}>{option.label}</option>
                    {/each}
                  </select>
                {:else}
                  <div class="radio-group" title={config.description}>
                    <label>
                      <input
                        type="radio"
                        name={config.key}
                        value="true"
                        checked={configValues[config.key] === true}
                        on:change={() => updateConfigValue(config.key, true)}
                      />
                      On
                    </label>
                    <label>
                      <input
                        type="radio"
                        name={config.key}
                        value="false"
                        checked={configValues[config.key] === false}
                        on:change={() => updateConfigValue(config.key, false)}
                      />
                      Off
                    </label>
                  </div>
                {/if}
              </div>
            {/each}
            <button class="action-button" type="button" on:click={saveConfigs} disabled={savingConfigs || !hasConfigChanges}>
              Save changes
            </button>
          {/if}
        </section>

        <button class="action-button" type="button" on:click={handleLogout} disabled={submitting}>
          Logout
        </button>
      </div>

      {#if authError}
        <p class="menu-error">{authError}</p>
      {/if}
      {#if configError}
        <p class="menu-error">{configError}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .user-menu-root { position: relative; }
  .user-trigger {
    width: calc(2.75rem * var(--mobile-ui-scale, 1));
    height: calc(2.75rem * var(--mobile-ui-scale, 1));
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--accent-soft);
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: background-color 120ms ease, border-color 120ms ease;
  }
  .user-trigger:hover { border-color: var(--accent); background: var(--surface-soft); }
  .user-trigger svg {
    width: calc(1.45rem * var(--mobile-ui-scale, 1));
    height: calc(1.45rem * var(--mobile-ui-scale, 1));
    fill: currentColor;
  }
  .menu-panel {
    position: absolute;
    right: 0;
    top: calc(100% + 0.55rem);
    width: min(18rem, 84vw);
    border-radius: 0.8rem;
    border: 1px solid var(--border);
    background: var(--bg);
    box-shadow: var(--shadow-panel);
    padding: 0.8rem;
    z-index: 100;
  }
  .user-details { display: flex; flex-direction: column; gap: 0.6rem; }
  .label { font-size: 0.75rem; color: var(--text-label); }
  .name { font-weight: 700; }
  .email { color: var(--muted); word-break: break-all; }
  .configs {
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 0.55rem 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .config-item { display: flex; flex-direction: column; gap: 0.35rem; }
  .config-item label { font-size: 0.86rem; font-family: inherit; }
  .config-item select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    font: inherit;
    border-radius: 0.45rem;
    padding: 0.35rem 0.45rem;
  }
  .radio-group { display: flex; gap: 0.6rem; font: inherit; font-size: 0.84rem; }
  .radio-group input { font: inherit; }
  .radio-group label { display: inline-flex; align-items: center; gap: 0.25rem; font-family: inherit; }
  .config-note { color: var(--muted); font-size: 0.82rem; }
  .action-button {
    margin-top: 0.2rem;
    border: 1px solid var(--accent);
    border-radius: 0.55rem;
    background: var(--accent);
    color: var(--text-on-accent);
    font: inherit;
    font-weight: 700;
    padding: 0.45rem 0.7rem;
    cursor: pointer;
  }
  .action-button:disabled { opacity: 0.6; cursor: not-allowed; }
  .menu-error { color: var(--error); margin-top: 0.55rem; font-size: 0.82rem; }
</style>
