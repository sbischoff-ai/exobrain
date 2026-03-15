import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import KnowledgeContentBlock from './KnowledgeContentBlock.svelte';
import KnowledgeContentBlockEventHarness from './KnowledgeContentBlockEventHarness.svelte';

describe('KnowledgeContentBlock', () => {
  it('renders markdown in view mode by default', async () => {
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
    expect(screen.queryByRole('textbox', { name: 'Markdown editor' })).not.toBeInTheDocument();
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

  it('clicking edit enters edit mode and shows a raw markdown textarea in a monospace-styled control', async () => {
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
    expect(editor).toHaveClass('markdown-editor');
    expect(editor).toHaveValue('# Title\n\n- item one\n- item two');
    expect(screen.getByRole('button', { name: 'Save changes' })).toHaveAttribute('type', 'button');
    expect(screen.queryByRole('heading', { name: 'Title' })).not.toBeInTheDocument();
  });

  it('Save changes exits edit mode and emits saveRequested with block id and markdown_content value', async () => {
    render(KnowledgeContentBlockEventHarness, {
      props: {
        blockId: 'block-4',
        markdown: '# Original\n\nInitial body'
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Edit block' }));

    const editor = screen.getByRole('textbox', { name: 'Markdown editor' });
    await fireEvent.input(editor, { target: { value: '# Updated\n\nEdited body' } });

    await fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.queryByRole('textbox', { name: 'Markdown editor' })).not.toBeInTheDocument();
    expect(screen.getByTestId('save-requested-event')).toHaveTextContent(
      JSON.stringify({ blockId: 'block-4', markdownContent: '# Updated\n\nEdited body' })
    );
  });
});
