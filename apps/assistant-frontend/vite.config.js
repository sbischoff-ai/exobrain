import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { createMockApiPlugin } from './mockApiPlugin';

const assistantBackendUrl = process.env.ASSISTANT_BACKEND_URL || 'http://localhost:8000';
const isVitest = process.env.VITEST === 'true';
const mockApiEnabled = process.env.ASSISTANT_FRONTEND_MOCK_API === 'true';

export default defineConfig({
  plugins: [sveltekit(), createMockApiPlugin({ enabled: mockApiEnabled })],
  ...(isVitest
    ? {
        resolve: {
          conditions: ['browser']
        }
      }
    : {}),
  server: {
    ...(mockApiEnabled
      ? {}
      : {
          proxy: {
            '/api': {
              target: assistantBackendUrl,
              changeOrigin: true
            }
          }
        }),
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.test.{js,ts}']
  }
});
