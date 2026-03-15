<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Streamdown } from 'svelte-streamdown';
  import StreamdownCode from 'svelte-streamdown/code';
  import StreamdownMath from 'svelte-streamdown/math';
  import StreamdownMermaid from 'svelte-streamdown/mermaid';
  import gruvboxDarkMedium from '@shikijs/themes/gruvbox-dark-medium';

  export let blockId: string;
  export let markdown: string;
  export let isSaving = false;

  const dispatch = createEventDispatcher<{
    saveRequested: { blockId: string; markdownContent: string };
  }>();

  let isEditing = false;
  let draftMarkdown = markdown;

  $: if (!isEditing) {
    draftMarkdown = markdown;
  }

  function saveChanges(): void {
    isEditing = false;
    dispatch('saveRequested', {
      blockId,
      markdownContent: draftMarkdown
    });
  }

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
</script>

<div class="assistant-markdown markdown-body content-block" data-block-id={blockId}>
  <button
    class="edit-block-button"
    type="button"
    aria-label="Edit block"
    disabled={isSaving}
    on:click={() => (isEditing = true)}
  >
    <svg viewBox="0 0 24 24" role="img" aria-hidden="true" focusable="false">
      <path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75L3 17.25Zm17.71-10.04a1.004 1.004 0 0 0 0-1.42l-2.5-2.5a1.004 1.004 0 0 0-1.42 0l-1.96 1.96 3.75 3.75 2.13-1.79Z" />
    </svg>
  </button>
  {#if isEditing}
    <div class="editor-area">
      <textarea
        class="markdown-editor"
        aria-label="Markdown editor"
        bind:value={draftMarkdown}
        spellcheck="false"
        disabled={isSaving}
      ></textarea>
      <button class="save-changes-button" type="button" disabled={isSaving} on:click={saveChanges}>Save changes</button>
    </div>
  {:else}
    <Streamdown
      content={markdown}
      theme={streamdownTheme}
      shikiTheme="gruvbox-dark-medium"
      shikiThemes={{ 'gruvbox-dark-medium': gruvboxDarkMedium }}
      components={{ code: StreamdownCode, math: StreamdownMath, mermaid: StreamdownMermaid }}
    />
  {/if}
</div>

<style>
  .markdown-body {
    color: var(--text);
    line-height: 1.5;
    position: relative;
  }

  .edit-block-button {
    position: absolute;
    top: var(--space-2, 0.5rem);
    right: var(--space-2, 0.5rem);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md, 0.5rem);
    background: var(--surface-elevated, var(--surface));
    color: inherit;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }

  .edit-block-button:disabled {
    opacity: 0.45;
    pointer-events: none;
  }

  .edit-block-button svg {
    width: 1rem;
    height: 1rem;
    fill: currentColor;
  }

  .content-block:hover .edit-block-button,
  .content-block:focus-within .edit-block-button {
    opacity: 1;
    pointer-events: auto;
  }

  .markdown-editor {
    width: 100%;
    min-height: 10rem;
    padding: var(--space-3, 0.75rem);
    border: 1px solid var(--border);
    border-radius: var(--radius-md, 0.5rem);
    background: var(--surface-elevated, var(--surface));
    color: inherit;
    font: inherit;
    font-family: var(
      --font-family-mono,
      ui-monospace,
      SFMono-Regular,
      Menlo,
      Monaco,
      Consolas,
      'Liberation Mono',
      'Courier New',
      monospace
    );
    white-space: pre;
    resize: vertical;
  }

  .editor-area {
    position: relative;
  }

  .save-changes-button {
    position: absolute;
    right: var(--space-2, 0.5rem);
    bottom: var(--space-2, 0.5rem);
    border: 1px solid var(--border);
    border-radius: var(--radius-md, 0.5rem);
    padding: var(--space-1, 0.25rem) var(--space-2, 0.5rem);
    background: var(--surface-elevated, var(--surface));
    color: inherit;
    font: inherit;
    cursor: pointer;
  }

  .save-changes-button:disabled {
    opacity: 0.6;
    cursor: wait;
  }
</style>
