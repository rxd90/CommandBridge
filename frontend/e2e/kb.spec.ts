import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('Knowledge Base', () => {
  test('KB page loads and shows article cards', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');
    const cards = page.locator('.cb_kb-card');
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('search filters articles', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');

    const allCount = await page.locator('.cb_kb-card').count();
    await page.locator('.cb_kb-search input').fill('login');
    await page.waitForTimeout(300);
    const filteredCount = await page.locator('.cb_kb-card').count();
    expect(filteredCount).toBeLessThan(allCount);
    expect(filteredCount).toBeGreaterThan(0);
  });

  test('clicking article navigates to article page', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');

    // Click first article card
    const firstCard = page.locator('.cb_kb-card').first();
    const title = await firstCard.locator('.cb_kb-card__title').textContent();
    await firstCard.click();

    // Should navigate to /kb/:id
    await expect(page).toHaveURL(/\/kb\/.+/);
    // Article metadata should be visible
    await page.waitForSelector('.cb_kb-article-meta');
  });

  test('L1 does not see New Article button', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');

    await expect(page.locator('text=New Article')).toBeHidden();
  });

  test('L2 sees New Article button', async ({ page }) => {
    await loginAs(page, 'L2-engineer');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');

    await expect(page.locator('a.cb_button', { hasText: 'New Article' })).toBeVisible();
  });
});
