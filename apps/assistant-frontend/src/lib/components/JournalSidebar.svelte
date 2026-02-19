<script>
  import { createEventDispatcher } from 'svelte';

  export let entries = [];
  export let currentReference = '';
  export let todayReference = '';
  export let collapsed = true;

  const dispatch = createEventDispatcher();

  const selectJournal = (reference) => dispatch('select', { reference });
  const toggleSidebar = () => dispatch('toggle');
</script>

{#if collapsed}
  <button class="sidebar-flag" type="button" on:click={toggleSidebar} aria-label="Open journals">
    <span aria-hidden="true">&gt;</span>
  </button>
{:else}
  <aside class="journal-overlay" aria-label="Journal sidebar">
    <button class="collapse-arrow" type="button" on:click={toggleSidebar} aria-label="Close journals">
      <span aria-hidden="true">&lt;</span>
    </button>

    <div class="journal-list" aria-label="Journal list">
      {#if todayReference}
        <button
          type="button"
          class="journal-item today"
          class:active={todayReference === currentReference}
          on:click={() => selectJournal(todayReference)}
        >
          Today · {todayReference}
        </button>
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
