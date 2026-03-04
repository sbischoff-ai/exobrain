import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import KnowledgeExplorerView from './KnowledgeExplorerView.svelte';

const serviceMocks = vi.hoisted(() => ({
  getCategoryTree: vi.fn(),
  getCategoryPages: vi.fn()
}));

vi.mock('$lib/services/knowledgeService', () => ({
  knowledgeService: {
    getCategoryTree: serviceMocks.getCategoryTree,
    getCategoryPages: serviceMocks.getCategoryPages
  }
}));

const { getCategoryTree, getCategoryPages } = serviceMocks;

describe('KnowledgeExplorerView', () => {
  it('loads overview cards and emits category/page navigation', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        { id: 'cat-a', name: 'Category A', page_count: 4, children: [] },
        { id: 'cat-b', name: 'Category B', page_count: 1, children: [] }
      ]
    });
    getCategoryPages.mockImplementation(async (id: string) => {
      if (id === 'cat-a') {
        return { pages: [{ id: 'page-a1', title: 'A1', summary: 'alpha' }] };
      }
      return { pages: [{ id: 'page-b1', title: 'B1', summary: null }] };
    });

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'overview' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Category A' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'A1' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Category A' }));
    await fireEvent.click(screen.getByRole('button', { name: 'A1' }));

    expect(getCategoryPages).toHaveBeenCalledWith('cat-a');
    expect(getCategoryPages).toHaveBeenCalledWith('cat-b');
  });

  it('renders category page breadcrumbs/tree and emits expansion updates', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'root',
          name: 'Root',
          page_count: 2,
          children: [
            {
              id: 'child',
              name: 'Child',
              page_count: 1,
              children: [{ id: 'leaf', name: 'Leaf', page_count: 1, children: [] }]
            }
          ]
        }
      ]
    });
    getCategoryPages.mockImplementation(async (id: string) => {
      if (id === 'child') {
        return { pages: [{ id: 'p-1', title: 'Child Page', summary: null }] };
      }
      return { pages: [] };
    });

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'category', id: 'child' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: 'Knowledge breadcrumbs' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Overview' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Root' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Child Page' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Overview' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Child Page' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Collapse Root' }));
  });
});
