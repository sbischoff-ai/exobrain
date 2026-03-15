import { fireEvent, render, screen } from '@testing-library/svelte';
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

  it('renders an accessible edit button with button type', () => {
    render(KnowledgeContentBlock, {
      props: {
        blockId: 'block-2',
        markdown: 'Content fragment'
      }
    });

    const button = screen.getByRole('button', { name: 'Edit block' });
    expect(button).toHaveAttribute('type', 'button');
  });

  it('enters edit mode with a multiline markdown editor initialized from markdown', async () => {
    render(KnowledgeContentBlock, {
      props: {
        blockId: 'block-3',
        markdown: '# Title\n\n- item one\n- item two'
      }
    });

    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Edit block' }));

    const editor = screen.getByRole('textbox', { name: 'Markdown editor' });
    expect(editor.tagName).toBe('TEXTAREA');
    expect(editor).toHaveValue('# Title\n\n- item one\n- item two');
    expect(screen.queryByRole('heading', { name: 'Title' })).not.toBeInTheDocument();
  });
});
