import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe('UserMenu', () => {
  it('loads and renders user configs in dropdown', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(await screen.findByText('User configs')).toBeInTheDocument();
    expect(screen.getByLabelText('Theme')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('enables Save changes only after config changes and emits theme updates', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'))
      .mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    const saveButton = screen.getByRole('button', { name: 'Save changes' });
    expect(saveButton).toBeDisabled();

    await fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'purple-intelligence' } });

    expect(saveButton).toBeEnabled();
  });

  it('resets unsaved config changes and emits persisted theme on close', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(configsResponse('gruvbox-dark'));

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    const themeSelect = screen.getByLabelText('Theme');

    await fireEvent.change(themeSelect, { target: { value: 'purple-intelligence' } });
    await fireEvent.keyDown(window, { key: 'Escape' });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    expect((screen.getByLabelText('Theme') as HTMLSelectElement).value).toBe('gruvbox-dark');
  });

  it('shows signed-in user details in dropdown', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({ ok: true, json: async () => ({ configs: [] }) } as Response);

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
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({ ok: true, json: async () => ({ configs: [] }) } as Response);

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
