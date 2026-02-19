import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import UserMenu from './UserMenu.svelte';

describe('UserMenu', () => {
  it('shows signed-in user details in dropdown', async () => {
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
