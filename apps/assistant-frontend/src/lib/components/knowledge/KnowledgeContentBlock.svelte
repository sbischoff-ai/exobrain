<script lang="ts">
  import { Streamdown } from 'svelte-streamdown';
  import StreamdownCode from 'svelte-streamdown/code';
  import StreamdownMath from 'svelte-streamdown/math';
  import StreamdownMermaid from 'svelte-streamdown/mermaid';
  import gruvboxDarkMedium from '@shikijs/themes/gruvbox-dark-medium';

  export let blockId: string;
  export let markdown: string;

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
  <Streamdown
    content={markdown}
    theme={streamdownTheme}
    shikiTheme="gruvbox-dark-medium"
    shikiThemes={{ 'gruvbox-dark-medium': gruvboxDarkMedium }}
    components={{ code: StreamdownCode, math: StreamdownMath, mermaid: StreamdownMermaid }}
  />
</div>

<style>
  .markdown-body {
    color: var(--text);
    line-height: 1.5;
  }
</style>
