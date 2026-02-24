<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';
  import StreamdownCode from 'svelte-streamdown/code';
  import gruvboxDarkMedium from '@shikijs/themes/gruvbox-dark-medium';
  import type { StoredMessage } from '$lib/models/journal';

  export let messages: StoredMessage[] = [];
  export let canLoadOlder = false;
  export let loadingOlder = false;
  export let onLoadOlder: () => void = () => {};
  export let containerElement: HTMLDivElement | undefined;

  const dispatch = createEventDispatcher<{ scroll: Event; wheel: WheelEvent }>();
  let expandedProcessStacks = new Set<string>();

  const streamdownTheme = {
    h1: { base: 'exo-md-heading' },
    h2: { base: 'exo-md-heading' },
    h3: { base: 'exo-md-heading' },
    h4: { base: 'exo-md-heading' },
    h5: { base: 'exo-md-heading' },
    h6: { base: 'exo-md-heading' },
    table: { base: 'exo-md-table-wrap', table: 'exo-md-table' },
    link: { base: 'exo-md-link' },
    blockquote: { base: 'exo-md-blockquote' },
    hr: { base: 'exo-md-hr' },
    th: { base: 'exo-md-th' },
    td: { base: 'exo-md-td' },
    li: { checkbox: 'exo-md-task-checkbox' },
    codespan: { base: 'exo-md-inline-code' },
    code: {
      container: 'exo-md-code-wrap',
      pre: 'exo-md-code-pre',
      base: 'exo-md-code',
      buttons: 'exo-md-control-group',
      language: 'exo-md-code-language'
    },
    components: {
      button: 'exo-md-control-button',
      popover: 'exo-md-control-popover'
    }
  };

  const toggleStack = (messageId: string): void => {
    const next = new Set(expandedProcessStacks);
    if (next.has(messageId)) {
      next.delete(messageId);
    } else {
      next.add(messageId);
    }
    expandedProcessStacks = next;
  };
</script>

<div
  class="messages"
  bind:this={containerElement}
  on:scroll={(event) => dispatch('scroll', event)}
  on:wheel={(event) => dispatch('wheel', event)}
>
  {#if canLoadOlder}
    <div class="load-older-wrap">
      <button class="load-older" type="button" on:click={onLoadOlder} disabled={loadingOlder}>
        {#if loadingOlder}Loading older messages...{:else}Load older messages{/if}
      </button>
    </div>
  {/if}

  {#each messages as message, index (message.clientMessageId ?? `${message.role}-${index}`)}
    <article
      class="message"
      class:user={message.role === 'user'}
      data-message-id={message.clientMessageId}
      data-message-role={message.role}
    >
      <div class="assistant-markdown" class:user-markdown={message.role === 'user'}>
        {#if message.role === 'assistant' && message.processInfos?.length}
          {@const stackExpanded = expandedProcessStacks.has(message.clientMessageId)}
          {@const orderedProcessInfos = stackExpanded ? message.processInfos : [...message.processInfos].reverse()}
          <div class="process-info-stack" class:expanded={stackExpanded}>
            {#if message.processInfos.length > 1}
              <button
                type="button"
                class="process-stack-toggle"
                aria-label={stackExpanded ? 'Fold tool call cards' : 'Unfold tool call cards'}
                aria-expanded={stackExpanded}
                on:click={() => toggleStack(message.clientMessageId)}
              >
                {stackExpanded ? '−' : '+'}
              </button>
            {/if}

            <div class="process-info-list" class:expanded={stackExpanded}>
              {#each orderedProcessInfos as info, stackIndex (info.id)}
                <section
                  class="process-info-card"
                  class:error={info.state === 'error'}
                  class:collapsed={!stackExpanded}
                  class:hidden-collapsed={!stackExpanded && stackIndex > 2}
                  style={`--stack-index:${Math.min(stackIndex, 2)}`}
                >
                  <p class="process-title">{info.title}</p>
                  <p class="process-description" class:muted={info.state !== 'pending'}>
                    {info.description}
                    {#if info.state === 'pending'}
                      <span class="loading-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span>
                    {/if}
                  </p>
                  {#if info.response}
                    <p class="process-response">{info.response}</p>
                  {/if}
                </section>
              {/each}
            </div>
          </div>
        {/if}
        <Streamdown
          content={message.content}
          theme={streamdownTheme}
          shikiTheme="gruvbox-dark-medium"
          shikiThemes={{ 'gruvbox-dark-medium': gruvboxDarkMedium }}
          components={{ code: StreamdownCode }}
        />
      </div>
    </article>
  {/each}
</div>
