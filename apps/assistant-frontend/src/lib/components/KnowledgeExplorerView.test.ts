import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KnowledgeExplorerView from './KnowledgeExplorerView.svelte';
import KnowledgeExplorerViewEventHarness from './KnowledgeExplorerViewEventHarness.svelte';

const serviceMocks = vi.hoisted(() => ({
  getCategoryTree: vi.fn(),
  getCategoryPages: vi.fn(),
  getPage: vi.fn(),
  patchPageContentBlocks: vi.fn()
}));

vi.mock('$lib/services/knowledgeService', () => ({
  knowledgeService: {
    getCategoryTree: serviceMocks.getCategoryTree,
    getCategoryPages: serviceMocks.getCategoryPages,
    getPage: serviceMocks.getPage,
    patchPageContentBlocks: serviceMocks.patchPageContentBlocks
  }
}));

const { getCategoryTree, getCategoryPages, getPage, patchPageContentBlocks } = serviceMocks;

describe('KnowledgeExplorerView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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
      expect(screen.getByText('A1')).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Category A' }));
    await fireEvent.click(screen.getByText('A1'));

    expect(getCategoryPages).toHaveBeenCalledWith('cat-a');
    expect(getCategoryPages).toHaveBeenCalledWith('cat-b');
  });

  it('emits only page navigation when clicking an overview page preview card', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [{ id: 'cat-a', name: 'Category A', page_count: 1, children: [] }]
    });
    getCategoryPages.mockResolvedValue({ pages: [{ id: 'page-a1', title: 'A1', summary: 'alpha' }] });

    render(KnowledgeExplorerViewEventHarness, {
      props: {
        explorerRoute: { type: 'overview' },
        expandedCategories: {}
      }
    });

    const pageCardTitle = await screen.findByText('A1');
    await fireEvent.click(pageCardTitle);

    expect(screen.getByTestId('emitted-routes')).toHaveTextContent(
      JSON.stringify([{ type: 'page', id: 'page-a1' }])
    );
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
      expect(screen.getByRole('heading', { name: 'Child Page' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Overview' }));
    await fireEvent.click(screen.getByText('Child Page'));
    await fireEvent.click(screen.getByRole('button', { name: 'Collapse Child' }));
  });



  it('collapses the visible branch when category toggle is clicked', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'root',
          name: 'Root',
          page_count: 2,
          children: [{ id: 'child', name: 'Child', page_count: 1, children: [] }]
        }
      ]
    });
    getCategoryPages.mockImplementation(async () => ({ pages: [] }));

    const { rerender } = render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'category', id: 'root' },
        expandedCategories: { root: true }
      }
    });

    const collapseButton = await screen.findByRole('button', { name: 'Collapse Root' });
    await fireEvent.click(collapseButton);

    await rerender({
      explorerRoute: { type: 'category', id: 'root' },
      expandedCategories: { root: false }
    });

    expect(screen.queryByRole('button', { name: 'Child' })).not.toBeInTheDocument();
  });

  it('renders breadcrumb navigation views across route transitions', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'root',
          name: 'Root',
          page_count: 1,
          children: [{ id: 'child', name: 'Child', page_count: 1, children: [] }]
        }
      ]
    });
    getCategoryPages.mockResolvedValue({ pages: [{ id: 'p-1', title: 'Child Page', summary: null }] });

    const { rerender } = render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'category', id: 'child' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: 'Knowledge breadcrumbs' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Overview' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Child/ })).toBeInTheDocument();
    });

    await rerender({ explorerRoute: { type: 'overview' }, expandedCategories: {} });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Root' })).toBeInTheDocument();
      expect(screen.queryByRole('navigation', { name: 'Knowledge breadcrumbs' })).not.toBeInTheDocument();
    });

    await rerender({ explorerRoute: { type: 'category', id: 'child' }, expandedCategories: {} });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Overview' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Root' })).toBeInTheDocument();
    });
  });

  it('renders knowledge page details with related links', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'event',
          name: 'Event',
          page_count: 2,
          children: [{ id: 'task', name: 'Task', page_count: 1, children: [] }]
        }
      ]
    });
    getCategoryPages.mockResolvedValue({ pages: [] });
    getPage.mockResolvedValue({
      id: 'page-1',
      title: 'Page Title',
      category_id: 'task',
      summary: null,
      properties: { source: 'docs', owner: 'team-knowledge' },
      content_blocks: [
        {
          block_id: 'blk-1',
          markdown: ['## Body', '', 'First fragment from block one.', '', 'Second fragment from block one.'].join(
            '\n'
          )
        },
        {
          block_id: 'blk-2',
          markdown: ['### Secondary body', '', 'Third fragment from block two.'].join('\n')
        }
      ],
      created_at: '2026-01-02T03:04:05Z',
      updated_at: '2026-01-03T04:05:06Z',
      links: [{ page_id: 'linked-1', title: 'Linked Page', summary: 'see also' }],
      category_breadcrumb: { path: [{ id: 'task', name: 'Task' }] }
    });

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'page', id: 'page-1' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Page Title' })).toBeInTheDocument();
      expect(screen.getByText('Created 2026/01/02 03:04 · Updated 2026/01/03 04:05')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Properties' })).toBeInTheDocument();
      expect(screen.getByText('source')).toBeInTheDocument();
      expect(screen.getByText('docs')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Related pages' })).toBeInTheDocument();
      expect(screen.getByText('Linked Page')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Event' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Task' })).toBeInTheDocument();
    });

    const meta = screen.getByText('Created 2026/01/02 03:04 · Updated 2026/01/03 04:05');
    const propertiesHeading = screen.getByRole('heading', { name: 'Properties' });
    const markdownHeading = screen.getByRole('heading', { name: 'Body' });
    const secondaryMarkdownHeading = screen.getByRole('heading', { name: 'Secondary body' });
    const firstFragment = screen.getByText('First fragment from block one.');
    const secondFragment = screen.getByText('Second fragment from block one.');
    const thirdFragment = screen.getByText('Third fragment from block two.');
    const allFragments = [firstFragment, secondFragment, thirdFragment];

    expect(meta.compareDocumentPosition(propertiesHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(propertiesHeading.compareDocumentPosition(markdownHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(markdownHeading.compareDocumentPosition(secondaryMarkdownHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    allFragments.slice(0, -1).forEach((fragment, index) => {
      const nextFragment = allFragments[index + 1];
      expect(fragment.compareDocumentPosition(nextFragment) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
    expect(document.querySelectorAll('.content-block')).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'Edit block' })).toHaveLength(2);

    expect(getPage).toHaveBeenCalledWith('page-1');
  });

  it('preserves category chain breadcrumbs for pages when API breadcrumb path is empty', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'root',
          name: 'Root',
          page_count: 1,
          children: [{ id: 'child', name: 'Child', page_count: 1, children: [] }]
        }
      ]
    });
    getCategoryPages.mockResolvedValue({ pages: [{ id: 'p-1', title: 'Child Page', summary: null }] });
    getPage.mockResolvedValue({
      id: 'p-1',
      title: 'Child Page',
      category_id: 'child',
      summary: null,
      properties: {},
      content_blocks: [{ block_id: 'blk-1', markdown: 'Body' }],
      created_at: null,
      updated_at: null,
      links: [],
      category_breadcrumb: { path: [] }
    });

    const { rerender } = render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'category', id: 'child' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      const breadcrumbs = screen.getByRole('navigation', { name: 'Knowledge breadcrumbs' });
      expect(within(breadcrumbs).getByRole('button', { name: 'Root' })).toBeInTheDocument();
      expect(within(breadcrumbs).getByText('Child')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Child Page' })).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByText('Child Page'));
    await rerender({ explorerRoute: { type: 'page', id: 'p-1' }, expandedCategories: {} });

    await waitFor(() => {
      expect(screen.getByLabelText('Knowledge page detail')).toBeInTheDocument();
      const breadcrumbs = screen.getByRole('navigation', { name: 'Knowledge breadcrumbs' });
      expect(within(breadcrumbs).getByRole('button', { name: 'Root' })).toBeInTheDocument();
      expect(within(breadcrumbs).getByRole('button', { name: 'Child' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Child Page' })).toBeInTheDocument();
    });
  });

  it('resolves page breadcrumbs from category_id when breadcrumb path is empty', async () => {
    getCategoryTree.mockResolvedValue({
      categories: [
        {
          id: 'root',
          name: 'Root',
          page_count: 1,
          children: [{ id: 'child', name: 'Child', page_count: 1, children: [] }]
        }
      ]
    });
    getCategoryPages.mockResolvedValue({ pages: [] });
    getPage.mockResolvedValue({
      id: 'p-1',
      title: 'Child Page',
      category_id: 'child',
      summary: null,
      properties: {},
      content_blocks: [{ block_id: 'blk-1', markdown: 'Body' }],
      created_at: null,
      updated_at: null,
      links: [],
      category_breadcrumb: { path: [] }
    });

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'page', id: 'p-1' },
        expandedCategories: {}
      }
    });

    await waitFor(() => {
      const breadcrumbs = screen.getByRole('navigation', { name: 'Knowledge breadcrumbs' });
      expect(within(breadcrumbs).getByRole('button', { name: 'Root' })).toBeInTheDocument();
      expect(within(breadcrumbs).getByRole('button', { name: 'Child' })).toBeInTheDocument();
    });
  });



  it('saves edited page blocks through patch endpoint and updates rendered markdown on success', async () => {
    getCategoryTree.mockResolvedValue({ categories: [] });
    getPage.mockResolvedValue({
      id: 'page-1',
      title: 'Page Title',
      category_id: null,
      summary: null,
      properties: {},
      content_blocks: [{ block_id: 'blk-1', markdown: '# Original\n\nInitial body' }],
      created_at: '2026-01-02T03:04:05Z',
      updated_at: '2026-01-03T04:05:06Z',
      links: [],
      category_breadcrumb: { path: [] }
    });
    patchPageContentBlocks.mockResolvedValue({
      page_id: 'page-1',
      updated_block_ids: ['blk-1'],
      updated_block_count: 1,
      status: 'updated'
    });

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'page', id: 'page-1' },
        expandedCategories: {}
      }
    });

    await screen.findByRole('heading', { name: 'Original' });

    await fireEvent.click(screen.getByRole('button', { name: 'Edit block' }));
    const editor = screen.getByRole('textbox', { name: 'Markdown editor' });
    await fireEvent.input(editor, { target: { value: '# Updated\n\nEdited body' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      expect(patchPageContentBlocks).toHaveBeenCalledWith('page-1', [
        { block_id: 'blk-1', markdown_content: '# Updated\n\nEdited body' }
      ]);
      expect(screen.getByRole('status')).toHaveTextContent('Block content saved successfully.');
      expect(screen.getByRole('heading', { name: 'Updated' })).toBeInTheDocument();
      expect(screen.getByText('Edited body')).toBeInTheDocument();
    });
  });

  it('keeps original block content and reports error when block patch fails', async () => {
    getCategoryTree.mockResolvedValue({ categories: [] });
    getPage.mockResolvedValue({
      id: 'page-1',
      title: 'Page Title',
      category_id: null,
      summary: null,
      properties: {},
      content_blocks: [{ block_id: 'blk-1', markdown: '# Original\n\nInitial body' }],
      created_at: '2026-01-02T03:04:05Z',
      updated_at: '2026-01-03T04:05:06Z',
      links: [],
      category_breadcrumb: { path: [] }
    });

    let rejectPatch: ((reason?: unknown) => void) | undefined;
    patchPageContentBlocks.mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          rejectPatch = reject;
        })
    );

    render(KnowledgeExplorerView, {
      props: {
        explorerRoute: { type: 'page', id: 'page-1' },
        expandedCategories: {}
      }
    });

    await screen.findByRole('heading', { name: 'Original' });

    await fireEvent.click(screen.getByRole('button', { name: 'Edit block' }));
    const editor = screen.getByRole('textbox', { name: 'Markdown editor' });
    await fireEvent.input(editor, { target: { value: '# Updated\n\nEdited body' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(screen.getByRole('button', { name: 'Edit block' })).toBeDisabled();

    rejectPatch?.(new Error('patch failed'));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(
        'Could not save block content. Your last saved content was restored.'
      );
      expect(screen.getByRole('heading', { name: 'Original' })).toBeInTheDocument();
      expect(screen.getByText('Initial body')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Updated' })).not.toBeInTheDocument();
    });
  });


});
