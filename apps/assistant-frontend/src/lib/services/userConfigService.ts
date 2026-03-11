import type { UserConfigItem } from '$lib/models/auth';
import { apiClient } from '$lib/services/apiClient';

interface UserConfigsResponse {
  configs: UserConfigItem[];
}

export const userConfigService = {
  async list(): Promise<UserConfigItem[]> {
    const response = await apiClient<UserConfigsResponse>('/api/users/me/configs');
    return response.configs;
  },

  async save(updates: Array<{ key: string; value: boolean | string }>): Promise<UserConfigItem[]> {
    const response = await apiClient<UserConfigsResponse>('/api/users/me/configs', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates: updates.map((update) => ({ key: update.key, value: update.value })) })
    });
    return response.configs;
  }
};
