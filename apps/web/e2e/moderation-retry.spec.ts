import { test, expect } from '@playwright/test';

test('Owner sees failed local scan and retries without opening approval', async ({ page }) => {
  test.skip(!process.env.CCE_E2E_MODERATION_SUBMISSION, 'Provisioned by the isolated Python moderation fixture');
  const base = process.env.CCE_E2E_BASE_URL || 'http://127.0.0.1:3100';
  page.setDefaultTimeout(10000);
  await page.goto(`${base}/login`);
  await page.getByLabel('E-posta').fill(process.env.CCE_E2E_OWNER_EMAIL!);
  await page.getByLabel('Şifre', { exact: false }).fill(process.env.CCE_E2E_OWNER_PASSWORD!);
  await page.getByRole('button', { name: 'Giriş yap' }).click();
  await expect(page).toHaveURL(/\/admin$/);

  await page.goto(`${base}/admin/reviews/${process.env.CCE_E2E_MODERATION_SUBMISSION}`);
  await expect(page.getByRole('heading', { name: 'Yerel tarama: ERROR' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'MODEL_UNAVAILABLE' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Revizyonu onayla' })).toBeDisabled();
  await expect(page.locator('details')).toContainText('#1 · ERROR · ERROR · MODEL_UNAVAILABLE');

  await page.getByRole('button', { name: 'Moderasyonu yeniden dene' }).click();
  await expect(page.getByRole('heading', { name: 'Yerel tarama: PENDING' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Moderasyonu yeniden dene' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Revizyonu onayla' })).toBeDisabled();
  await expect(page.locator('details')).toContainText('#1 · ERROR · ERROR · MODEL_UNAVAILABLE');
});
