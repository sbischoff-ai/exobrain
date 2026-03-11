import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import PageCard from './PageCard.svelte';

describe('PageCard', () => {
  it('applies truncation classes for title and summary content', () => {
    const { container } = render(PageCard, {
      props: {
        page: {
          id: 'page-1',
          title: 'A very long page title that should truncate to keep card rows stable',
          summary:
            'A very long summary that should be clamped so that overview and category cards stay compact and readable.'
        }
      }
    });

    expect(screen.getByRole('button', { name: /A very long page title/ })).toHaveClass('page-card');
    expect(container.querySelector('.page-link')).toHaveClass('truncate');
    expect(container.querySelector('p')).toHaveClass('summary-clamp');
  });

  it('stops click propagation so parent category cards are not activated', async () => {
    const { container } = render(PageCard, {
      props: {
        page: {
          id: 'page-2',
          title: 'Nested Page',
          summary: null
        }
      }
    });

    const parentClick = vi.fn();
    container.addEventListener('click', parentClick);

    await fireEvent.click(screen.getByRole('button', { name: 'Nested Page' }));

    expect(parentClick).not.toHaveBeenCalled();
  });
});
