import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AssistantWorkspace from './AssistantWorkspace.svelte';

const baseProps = {
  user: { name: 'Test User', email: 'test.user@exobrain.local' },
  journalEntries: [{ reference: '2026/02/19' }, { reference: '2026/01/01' }],
  currentReference: '2026/02/19',
  todayReference: '2026/02/19',
  messages: [{ role: 'assistant', content: 'hello', clientMessageId: 'a-1' }],
  knowledgeUpdateTooltip: 'Update knowledge base'
};

describe('AssistantWorkspace', () => {
  it('updates mode toggle button tooltip/label and icon when mode changes', async () => {
    const { rerender, container } = render(AssistantWorkspace, {
      props: {
        ...baseProps,
        viewMode: 'chat'
      }
    });

    const toKnowledge = screen.getByRole('button', { name: 'Switch to Knowledge Explorer' });
    expect(toKnowledge).toHaveAttribute('title', 'Switch to Knowledge Explorer');
    expect(container.querySelector('.header-action-button path')?.getAttribute('d')).toContain('M6 3a3 3');

    await rerender({ ...baseProps, viewMode: 'knowledge' });

    const toChat = screen.getByRole('button', { name: 'Switch to Journal Chat' });
    expect(toChat).toHaveAttribute('title', 'Switch to Journal Chat');
    expect(container.querySelector('.header-action-button path')?.getAttribute('d')).toContain('M4 4h16');
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
