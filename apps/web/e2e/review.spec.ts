import { test, expect, type Page } from '@playwright/test';

test('Owner requests changes, contributor revises, Owner rejects; moderation fails closed', async ({ browser }) => {
  test.skip(!process.env.CCE_E2E_OWNER_EMAIL, 'Provisioned by the isolated Python review fixture');
  const ownerContext = await browser.newContext();
  const contributorContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const contributor = await contributorContext.newPage();
  owner.setDefaultTimeout(10000);
  contributor.setDefaultTimeout(10000);
  const base = process.env.CCE_E2E_BASE_URL || 'http://127.0.0.1:3100';
  async function login(page: Page, email: string, password: string) {
    await page.goto(`${base}/login`);
    await page.getByLabel('E-posta').fill(email);
    await page.getByLabel('Şifre', { exact: false }).fill(password);
    await page.getByRole('button', { name: 'Giriş yap' }).click();
    await expect(page).toHaveURL(/\/(admin|contributor)$/);
  }
  try {
    await login(contributor, process.env.CCE_E2E_CONTRIBUTOR_EMAIL!, process.env.CCE_E2E_CONTRIBUTOR_PASSWORD!);
    await login(owner, process.env.CCE_E2E_OWNER_EMAIL!, process.env.CCE_E2E_OWNER_PASSWORD!);
    await contributor.goto(`${base}/admin/reviews`);
    await expect(contributor).toHaveURL(/\/contributor$/);
    await contributor.goto(`${base}/contributor/drafts/new`);
    await contributor.getByLabel('İsim', { exact: true }).fill('İnceleme Deniz');
    await contributor.getByLabel('Kısa tanıtım', { exact: true }).fill('Meraklı bir arşivci.');
    await contributor.getByLabel('Geçmiş hikâyesi', { exact: true }).fill('Sahil kentinde büyümüş yetişkin karakter.');
    await contributor.getByLabel('Karakter açıkça yetişkin görünür.').check();
    await contributor.getByLabel('Gerçek bir kişinin', { exact: false }).check();
    await contributor.getByRole('button', { name: 'Kaydet ve ön izle' }).click();
    await expect(contributor).toHaveURL(/\/drafts\/[0-9a-f-]+$/);
    const id = contributor.url().split('/').at(-1)!;
    await contributor.getByRole('button', { name: 'İncelemeye gönder' }).click();
    await expect(contributor.getByText('SUBMITTED', { exact: true })).toBeVisible();
    await owner.goto(`${base}/admin/reviews`);
    await owner.getByRole('link', { name: 'İnceleme Deniz', exact: true }).click();
    await owner.getByRole('button', { name: 'İncelemeyi başlat' }).click();
    await expect(owner.getByRole('heading', { name: 'Moderasyon: ERROR' })).toBeVisible();
    await expect(owner.getByRole('button', { name: 'Revizyonu onayla' })).toBeDisabled();
    await owner.getByLabel('Karar gerekçesi').fill('Geçmişteki arşiv deneyimini açıkla.');
    await owner.getByRole('button', { name: 'Değişiklik iste' }).click();
    await expect(owner.locator('strong').filter({ hasText: /^CHANGES_REQUESTED$/ })).toBeVisible();
    await contributor.reload();
    await expect(contributor.getByText('Geçmişteki arşiv deneyimini açıkla.', { exact: true })).toBeVisible();
    await contributor.getByRole('button', { name: 'Yeni revizyon taslağı aç' }).click();
    await expect(contributor.getByLabel('İsim', { exact: true })).toBeEnabled();
    await contributor.getByLabel('İsim', { exact: true }).fill('Yeni Deniz');
    await contributor.getByRole('button', { name: 'Kaydet ve ön izle' }).click();
    await expect(contributor.getByRole('button', { name: 'İncelemeye gönder' })).toBeEnabled();
    await contributor.getByRole('button', { name: 'İncelemeye gönder' }).click();
    await expect(contributor.getByText('SUBMITTED', { exact: true })).toBeVisible();
    await owner.goto(`${base}/admin/reviews/${id}`);
    await owner.getByText('Revizyon 2 — Yeni Deniz', { exact: true }).click();
    await expect(owner.getByText('Önce: "İnceleme Deniz"', { exact: true })).toBeVisible();
    await owner.getByRole('button', { name: 'İncelemeyi başlat' }).click();
    await owner.getByLabel('Karar gerekçesi').fill('Bu başvuruyu test kapsamında reddediyorum.');
    await owner.getByRole('button', { name: 'Reddet', exact: true }).click();
    await expect(owner.locator('strong').filter({ hasText: /^REJECTED$/ })).toBeVisible();
    await contributor.reload();
    await expect(contributor.getByText('Bu başvuruyu test kapsamında reddediyorum.', { exact: true })).toBeVisible();
    await expect(contributor.getByLabel('İsim', { exact: true })).toBeDisabled();
  } finally {
    // Cleanup must not hide the failing interaction when Playwright has timed out.
    await Promise.allSettled([ownerContext.close(), contributorContext.close()]);
  }
});
