import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const assistantBackendUrl = process.env.ASSISTANT_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/api': {
        target: assistantBackendUrl,
        changeOrigin: true
      }
    }
  },
  resolve: {
    conditions: ['browser']
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.js'],
    include: ['src/**/*.test.js']
  }
});
