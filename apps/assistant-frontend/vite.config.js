import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const assistantBackendUrl = process.env.ASSISTANT_BACKEND_URL || 'http://localhost:8000';
const isVitest = process.env.VITEST === 'true';

export default defineConfig({
  plugins: [sveltekit()],
  ...(isVitest
    ? {
        resolve: {
          conditions: ['browser']
        }
      }
    : {}),
  server: {
    proxy: {
      '/api': {
        target: assistantBackendUrl,
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.test.{js,ts}']
  }
});
