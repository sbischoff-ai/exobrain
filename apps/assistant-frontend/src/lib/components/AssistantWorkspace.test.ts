import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AssistantWorkspace from './AssistantWorkspace.svelte';

const baseProps = {
  user: { name: 'Test User', email: 'test.user@exobrain.local' },
  journalEntries: [
    { id: 'journal-1', reference: '2026/02/19', message_count: 1 },
    { id: 'journal-2', reference: '2026/01/01', message_count: 1 }
  ],
  currentReference: '2026/02/19',
  todayReference: '2026/02/19',
  messages: [{ role: 'assistant', content: 'hello', clientMessageId: 'a-1' }],
  knowledgeUpdateTooltip: 'Update knowledge base'
};

describe('AssistantWorkspace', () => {
  it('updates mode toggle button tooltip/label and icon when mode changes', async () => {
    const { rerender } = render(AssistantWorkspace, {
      props: {
        ...baseProps,
        viewMode: 'chat'
      }
    });

    const toKnowledge = screen.getByRole('button', { name: 'Switch to Knowledge Explorer' });
    expect(toKnowledge).toHaveAttribute('title', 'Switch to Knowledge Explorer');
    const toKnowledgeIcon = toKnowledge.querySelector('path');
    expect(toKnowledgeIcon?.getAttribute('d')).toContain('M31,7.663L2.516,0.067');

    await rerender({ ...baseProps, viewMode: 'knowledge' });

    const toChat = screen.getByRole('button', { name: 'Switch to Journal Chat' });
    expect(toChat).toHaveAttribute('title', 'Switch to Journal Chat');
    const toChatIcon = toChat.querySelector('path');
    expect(toChatIcon?.getAttribute('d')).toContain('M4 4h16');
  });



  it('renders theme toggle button label for current theme', async () => {
    const { rerender } = render(AssistantWorkspace, {
      props: {
        ...baseProps,
        theme: 'gruvbox-dark'
      }
    });

    expect(screen.getByRole('button', { name: 'Switch to purple-intelligence theme' })).toHaveAttribute(
      'title',
      'Switch to purple-intelligence theme'
    );

    await rerender({ ...baseProps, theme: 'purple-intelligence' });

    expect(screen.getByRole('button', { name: 'Switch to gruvbox-dark theme' })).toHaveAttribute(
      'title',
      'Switch to gruvbox-dark theme'
    );
  });

  it('renders expected root view for each mode', async () => {
    const { rerender } = render(AssistantWorkspace, {
      props: {
        ...baseProps,
        viewMode: 'chat'
      }
    });

    expect(screen.getByRole('button', { name: 'Open journals' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Knowledge explorer')).not.toBeInTheDocument();

    await rerender({ ...baseProps, viewMode: 'knowledge' });

    expect(screen.getByLabelText('Knowledge explorer')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open journals' })).not.toBeInTheDocument();
  });
});
