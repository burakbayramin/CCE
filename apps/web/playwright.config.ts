import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0, timeout: 45000,
  use: {
    baseURL: process.env.CCE_E2E_BASE_URL || 'http://127.0.0.1:3100',
    channel: process.env.CCE_BROWSER_CHANNEL || undefined,
    trace: 'off', screenshot: 'off', video: 'off',
  },
});
