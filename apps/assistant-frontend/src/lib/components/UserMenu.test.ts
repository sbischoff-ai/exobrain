import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import UserMenu from './UserMenu.svelte';

describe('UserMenu', () => {
  it('loads and renders user configs in dropdown', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        configs: [
          {
            key: 'frontend.theme',
            name: 'Theme',
            config_type: 'choice',
            description: 'Select the assistant frontend theme',
            options: [{ value: 'gruvbox-dark', label: 'Gruvbox Dark' }],
            value: 'gruvbox-dark',
            default_value: 'gruvbox-dark',
            using_default: true
          }
        ]
      })
    } as Response);

    render(UserMenu, {
      props: {
        user: { name: 'Alice', email: 'alice@example.com' }
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    expect(await screen.findByText('User configs')).toBeInTheDocument();
    expect(screen.getByLabelText('Theme')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument();
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
