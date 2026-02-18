import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('Login page', () => {
  test('shows local dev mode label and user buttons', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('.cb_login__dev-label')).toContainText('Local dev mode');
    const buttons = page.locator('.cb_login__user-btn');
    await expect(buttons).toHaveCount(4);
  });

  test('clicking a user logs in and redirects to home', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await expect(page.locator('.cb_nav-user__name')).toContainText('Alice McGregor');
  });

  test('L1 shows correct role badge', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await expect(page.locator('.cb_nav-user .cb_tag')).toContainText('L1 Operator');
  });

  test('L2 shows correct role badge', async ({ page }) => {
    await loginAs(page, 'L2-engineer');
    await expect(page.locator('.cb_nav-user .cb_tag')).toContainText('L2 Engineer');
  });

  test('L3 shows correct role badge', async ({ page }) => {
    await loginAs(page, 'L3-admin');
    await expect(page.locator('.cb_nav-user .cb_tag')).toContainText('L3 Admin');
  });
});
