<script lang="ts">
  import type { ComponentEvents } from 'svelte';
  import KnowledgeContentBlock from './KnowledgeContentBlock.svelte';

  export let blockId: string;
  export let markdown: string;

  let lastEvent: ComponentEvents<KnowledgeContentBlock>['saveRequested']['detail'] | null = null;
</script>

<KnowledgeContentBlock
  {blockId}
  {markdown}
  on:saveRequested={(event) => {
    lastEvent = event.detail;
  }}
/>

<output data-testid="save-requested-event">{JSON.stringify(lastEvent)}</output>
