import type { CurrentUser, LoginRequest } from '$lib/models/auth';
import { apiClient, apiClientAllowUnauthorized } from '$lib/services/apiClient';

/** Service that encapsulates assistant auth-related API calls. */
export const authService = {
  getCurrentUser(): Promise<CurrentUser | null> {
    return apiClientAllowUnauthorized<CurrentUser>('/api/users/me');
  },

  async login(email: string, password: string): Promise<void> {
    const payload: LoginRequest = {
      email,
      password,
      session_mode: 'web',
      issuance_policy: 'session'
    };

    await apiClient<unknown>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  },

  async logout(): Promise<void> {
    const response = await fetch('/api/auth/logout', { method: 'POST' });
    if (!response.ok && response.status !== 204) {
      throw new Error(`logout failed: ${response.status}`);
    }
  }
};
