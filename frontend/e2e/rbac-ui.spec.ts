import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('RBAC UI enforcement', () => {
  test('L1 cannot see Admin or Activity nav links', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await expect(page.locator('.cb_nav__link', { hasText: 'Admin' })).toBeHidden();
    await expect(page.locator('.cb_nav__link', { hasText: 'Activity' })).toBeHidden();
  });

  test('L3 sees Admin and Activity nav links', async ({ page }) => {
    await loginAs(page, 'L3-admin');
    await expect(page.locator('.cb_nav__link', { hasText: 'Admin' })).toBeVisible();
    await expect(page.locator('.cb_nav__link', { hasText: 'Activity' })).toBeVisible();
  });

  test('L1 does not see New Article button on KB page', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');
    await expect(page.locator('a.cb_button', { hasText: 'New Article' })).toBeHidden();
  });

  test('L2 sees New Article button on KB page', async ({ page }) => {
    await loginAs(page, 'L2-engineer');
    await page.goto('/kb');
    await page.waitForSelector('.cb_kb-card');
    await expect(page.locator('a.cb_button', { hasText: 'New Article' })).toBeVisible();
  });
});
