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

<aside class="journal-sidebar" class:collapsed>
  <button class="sidebar-toggle" type="button" on:click={toggleSidebar}>
    {collapsed ? 'Show journals' : 'Hide journals'}
  </button>

  {#if !collapsed}
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
  {/if}
</aside>
