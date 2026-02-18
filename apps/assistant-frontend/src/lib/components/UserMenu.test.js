import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserMenu from './UserMenu.svelte';

describe('UserMenu', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders login form when user is unauthenticated and can log in successfully', async () => {
    // Case steps:
    // 1) Initial user probe returns 401 (not logged in)
    // 2) Login succeeds
    // 3) Component reloads current user and displays signed-in details
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ name: 'Alice', email: 'alice@example.com' })
      });

    render(UserMenu);

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));

    const emailInput = await screen.findByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');

    await fireEvent.input(emailInput, { target: { value: 'alice@example.com' } });
    await fireEvent.input(passwordInput, { target: { value: 'password123' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(screen.getByText('Signed in as')).toBeInTheDocument();
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'alice@example.com',
        password: 'password123',
        session_mode: 'web',
        issuance_policy: 'session'
      })
    });
  });

  it('shows an explicit error message when login fails', async () => {
    // This validates the unhappy path: failed credentials should display feedback
    // and keep the user in the login form for retry.
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({ ok: false, status: 401 });

    render(UserMenu);

    await fireEvent.click(screen.getByRole('button', { name: 'Open user menu' }));
    await fireEvent.input(await screen.findByLabelText('Email'), {
      target: { value: 'alice@example.com' }
    });
    await fireEvent.input(screen.getByLabelText('Password'), {
      target: { value: 'wrong-pass' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => {
      expect(
        screen.getByText('Login failed. Check your credentials and try again.')
      ).toBeInTheDocument();
    });
  });
});
