import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('Navigation', () => {
  test('L1 sees core nav links but not Admin or Activity', async ({ page }) => {
    await loginAs(page, 'L1-operator');

    await expect(page.locator('.cb_nav__link', { hasText: 'Home' })).toBeVisible();
    await expect(page.locator('.cb_nav__link', { hasText: 'Knowledge Base' })).toBeVisible();
    await expect(page.locator('.cb_nav__link', { hasText: 'Service Status' })).toBeVisible();
    await expect(page.locator('.cb_nav__link', { hasText: 'Actions' })).toBeVisible();

    await expect(page.locator('.cb_nav__link', { hasText: 'Admin' })).toBeHidden();
    await expect(page.locator('.cb_nav__link', { hasText: 'Activity' })).toBeHidden();
  });

  test('L3 sees Admin and Activity nav links', async ({ page }) => {
    await loginAs(page, 'L3-admin');

    await expect(page.locator('.cb_nav__link', { hasText: 'Admin' })).toBeVisible();
    await expect(page.locator('.cb_nav__link', { hasText: 'Activity' })).toBeVisible();
  });

  test('all pages render without errors', async ({ page }) => {
    await loginAs(page, 'L3-admin');

    const pages = ['/', '/actions', '/kb', '/status', '/activity', '/admin'];
    for (const path of pages) {
      await page.goto(path);
      await expect(page.locator('.cb_error-boundary')).toBeHidden();
    }
  });

  test('unknown route shows Page Not Found', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/nonexistent-page');
    await expect(page.locator('text=Page Not Found')).toBeVisible();
  });
});
