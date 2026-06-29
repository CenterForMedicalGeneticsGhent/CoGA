import { type Page } from '@playwright/test';

export const E2E_EMAIL = process.env.E2E_USER_EMAIL || 'e2e.playwright@example.com';
export const E2E_PASSWORD = process.env.E2E_USER_PASSWORD || 'e2e-playwright-pw';
export const GOLDEN_FAMILY = 'FAM_TRIO';

/** Log in via the real login form and wait until we've left /login. */
export async function login(page: Page): Promise<void> {
  await page.goto('/login');
  await page.locator('input[type="email"]').fill(E2E_EMAIL);
  await page.locator('input[type="password"]').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: /login|signing in/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20_000 });
}
