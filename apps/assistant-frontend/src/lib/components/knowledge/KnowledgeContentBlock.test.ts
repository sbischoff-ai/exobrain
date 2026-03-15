import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import KnowledgeContentBlock from './KnowledgeContentBlock.svelte';

describe('KnowledgeContentBlock', () => {
  it('renders markdown in a styled content block wrapper', async () => {
    const { container } = render(KnowledgeContentBlock, {
      props: {
        blockId: 'block-1',
        markdown: '## Body\n\nContent fragment'
      }
    });

    expect(await screen.findByRole('heading', { name: 'Body' })).toBeInTheDocument();

    const block = container.querySelector('[data-block-id="block-1"]');
    expect(block).toHaveClass('assistant-markdown', 'markdown-body', 'content-block');
    expect(screen.getByText('Content fragment')).toBeInTheDocument();
  });
});
