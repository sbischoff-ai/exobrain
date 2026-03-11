import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import UserMenu from './UserMenu.svelte';

function configsResponse(theme: string) {
  return {
    ok: true,
    json: async () => ({
      configs: [
        {
          key: 'frontend.theme',
          name: 'Theme',
          config_type: 'choice',
          description: 'Select the assistant frontend theme',
          options: [
            { value: 'gruvbox-dark', label: 'Gruvbox Dark' },
            { value: 'purple-intelligence', label: 'Purple Intelligence' }
          ],
          value: theme,
          default_value: 'gruvbox-dark',
          using_default: theme === 'gruvbox-dark'
        }
      ]
    })
  } as Response;
}


beforeEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('UserMenu', () => {
  it('loads and renders user configs in dropdown', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(await screen.findByText('User configs')).toBeInTheDocument();
    expect(screen.getByLabelText('Theme')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('enables Save changes only after config changes and emits theme updates', async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'))
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    const saveButton = await screen.findByRole('button', { name: 'Save changes' });
    expect(saveButton).toBeDisabled();

    await fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'purple-intelligence' } });

    expect(saveButton).toBeEnabled();
  });

  it('resets unsaved config changes and emits persisted theme on close', async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'))
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    const themeSelect = await screen.findByLabelText('Theme');

    await fireEvent.change(themeSelect, { target: { value: 'purple-intelligence' } });
    await fireEvent.keyDown(window, { key: 'Escape' });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeDisabled();
    expect((screen.getByLabelText('Theme') as HTMLSelectElement).value).toBe('gruvbox-dark');
  });

  it('shows success message after saving config changes', async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'))
      .mockResolvedValueOnce(configsResponse('purple-intelligence'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.change(await screen.findByLabelText('Theme'), { target: { value: 'purple-intelligence' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Config changes saved.');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('shows signed-in user details in dropdown', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, json: async () => ({ configs: [] }) } as Response);

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(screen.getByText('Signed in as')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
  });

  it('calls parent logout handler when logout is clicked', async () => {
    const onLogout = vi.fn().mockResolvedValue(undefined);
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, json: async () => ({ configs: [] }) } as Response);

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' },
        onLogout
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => {
      expect(onLogout).toHaveBeenCalledTimes(1);
    });
  });
});
