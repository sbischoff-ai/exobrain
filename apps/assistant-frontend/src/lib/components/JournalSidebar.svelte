<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  import type { JournalEntry } from '$lib/models/journal';

  export let entries: JournalEntry[] = [];
  export let currentReference = '';
  export let todayReference = '';
  export let collapsed = true;

  const dispatch = createEventDispatcher<{ select: { reference: string }; toggle: null }>();

  const selectJournal = (reference: string): void => {
    dispatch('select', { reference });
  };
  const toggleSidebar = (): void => {
    dispatch('toggle', null);
  };
</script>

{#if collapsed}
  <button class="sidebar-flag" type="button" on:click={toggleSidebar} aria-label="Open journals">
    <svg viewBox="0 0 20 20" aria-hidden="true" class="arrow-icon right">
      <path d="M7 4 L13 10 L7 16" />
    </svg>
  </button>
{:else}
  <aside class="journal-overlay" aria-label="Journal sidebar">
    <button class="collapse-arrow" type="button" on:click={toggleSidebar} aria-label="Close journals">
      <svg viewBox="0 0 20 20" aria-hidden="true" class="arrow-icon left">
        <path d="M13 4 L7 10 L13 16" />
      </svg>
    </button>

    <div class="journal-list" aria-label="Journal list">
      {#if todayReference}
        <div class="journal-today-wrap">
          <button
            type="button"
            class="journal-item today"
            class:active={todayReference === currentReference}
            on:click={() => selectJournal(todayReference)}
          >
            Today · {todayReference}
          </button>
        </div>
      {/if}

      {#each entries as entry (entry.reference)}
        {#if entry.reference !== todayReference}
          <button
            type="button"
            class="journal-item"
            class:active={entry.reference === currentReference}
            on:click={() => selectJournal(entry.reference)}
          >
            {entry.reference}
          </button>
        {/if}
      {/each}
    </div>
  </aside>
{/if}
