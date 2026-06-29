import { defineConfig } from '@playwright/test';

// Browser end-to-end (M6). Drives a real Chromium against a real running stack:
// a uvicorn backend + the Vite dev server (which proxies /api to the backend).
// Seed the data first (golden trio + a known e2e user):
//   RUN_INTEGRATION=1 python scripts/seed_playwright_e2e.py
// then: npx playwright test   (locally pass E2E_PYTHON=/path/to/python with deps).

const BACKEND = 'http://127.0.0.1:8000';
const FRONTEND_PORT = 5173;
const PY = process.env.E2E_PYTHON || 'python';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    headless: true,
    browserName: 'chromium',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      // Backend reads Postgres/ClickHouse creds from .env; we override APP_ENV +
      // the bootstrap flags so startup stays light (no reference/HPO/gene loads).
      command: `${PY} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`,
      cwd: '..',
      url: `${BACKEND}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: 'test',
        REFERENCE_BOOTSTRAP_ENABLED: 'false',
        HPO_BOOTSTRAP_ON_STARTUP: 'false',
        GENE_REFERENCE_BOOTSTRAP_ON_STARTUP: 'false',
      },
    },
    {
      // Bind IPv4 explicitly: vite defaults to localhost (often ::1), which the
      // 127.0.0.1 readiness probe / baseURL can't reach.
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { VITE_DEV_API_PROXY_TARGET: BACKEND },
    },
  ],
});
