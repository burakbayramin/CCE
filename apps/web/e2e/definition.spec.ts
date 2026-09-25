import { test, expect } from '@playwright/test';

test('Owner compiles an approved fixture once without activating a character', async ({ page }) => {
  test.skip(!process.env.CCE_E2E_DEFINITION_SUBMISSION, 'Provisioned by isolated Python fixture');
  await page.goto('/login');
  await page.getByLabel('E-posta').fill(process.env.CCE_E2E_OWNER_EMAIL!);
  await page.getByLabel('Şifre', { exact: false }).fill(process.env.CCE_E2E_OWNER_PASSWORD!);
  await page.getByRole('button', { name: 'Giriş yap' }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.goto(`/admin/reviews/${process.env.CCE_E2E_DEFINITION_SUBMISSION}`);
  await page.getByRole('button', { name: 'Onaylı tanımı derle' }).click();
  await expect(page.getByText('TEST FİXTURE — gerçek aktivasyon izni değildir.', { exact: true })).toBeVisible();
  const hash = await page.getByText(/^SHA-256:/).innerText();
  expect(hash).toMatch(/^SHA-256: [0-9a-f]{64}$/);
  await expect(page.getByText('APPROVED', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Onaylı tanımı derle' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(hash, { exact: true })).toBeVisible();
  await expect(page.getByText('Bu işlem yalnız onaylı kaynağı derler.', { exact: false })).toBeVisible();
});
