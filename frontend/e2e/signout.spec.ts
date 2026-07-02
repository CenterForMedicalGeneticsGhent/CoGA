import { expect, test, type Page } from '@playwright/test';

import { GOLDEN_FAMILY, login } from './helpers';

/** Parse the current signed-out version from the report footer (0 if none yet). */
async function currentVersion(page: Page): Promise<number> {
  const banner = page.getByText(/Signed out/i).first();
  if (!(await banner.isVisible().catch(() => false))) return 0;
  const text = await banner.innerText();
  const match = text.match(/version\s+(\d+)/i);
  return match ? Number.parseInt(match[1], 10) : 0;
}

test('signs out the family report from the browser (with gate handling)', async ({ page }) => {
  // The evidence-drift gate is a native confirm() — auto-accept if it fires.
  page.on('dialog', (dialog) => void dialog.accept().catch(() => {}));

  await login(page);
  await page.goto(`/families/${GOLDEN_FAMILY}/report`);

  // The seed tagged a variant for reporting, so the report is non-empty...
  await expect(page.getByText(/No variants are currently tagged for reporting/i)).toHaveCount(0);
  const signOutButton = page.getByRole('button', { name: /sign out report|amend sign-out/i });
  await expect(signOutButton).toBeVisible();

  const before = await currentVersion(page);
  await signOutButton.click();

  // The sample-integrity gate (#330) requires an acknowledgement when an asserted
  // relationship can't be verified — the seeded trio's sparse genotypes give too few
  // shared sites, so the acknowledge-with-reason modal appears. WAIT for it (its reason
  // field is a stable anchor; a plain isVisible() check does not wait and races the
  // async POST -> 409 -> render), record a reason, and override once the button enables.
  // Guarded so the test still passes if a denser seed later makes the QC verifiable.
  const qcReason = page.locator('#qc-ack-reason');
  const gated = await qcReason
    .waitFor({ state: 'visible', timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  if (gated) {
    await qcReason.fill('e2e QC override — relatedness not assessable on seed data');
    const overrideButton = page.getByRole('button', { name: /sign out anyway/i });
    await expect(overrideButton).toBeEnabled();
    await overrideButton.click();
  }

  // A freshly signed-out version is shown, and the version advanced.
  await expect(page.getByText(/Signed out/i).first()).toBeVisible({ timeout: 20_000 });
  await expect.poll(() => currentVersion(page), { timeout: 20_000 }).toBeGreaterThan(before);
});
