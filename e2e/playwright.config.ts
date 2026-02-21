import { defineConfig, devices } from '@playwright/test';

const useExistingServer = process.env.E2E_USE_EXISTING_SERVER === 'true';

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  webServer: useExistingServer
    ? undefined
    : {
        command: 'bash ../scripts/agent/run-assistant-frontend-mock.sh',
        port: 5173,
        timeout: 120_000,
        reuseExistingServer: true
      },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
});
