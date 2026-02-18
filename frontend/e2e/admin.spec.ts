import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('Admin page', () => {
  test('L3 can access admin page and see user table', async ({ page }) => {
    await loginAs(page, 'L3-admin');
    await page.goto('/admin');

    await expect(page.locator('text=Admin Panel')).toBeVisible();
    // User table should have rows
    await page.waitForSelector('.cb_admin-table');
    const rows = page.locator('.cb_admin-table tbody tr');
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test('admin page shows all users from users.json', async ({ page }) => {
    await loginAs(page, 'L3-admin');
    await page.goto('/admin');
    await page.waitForSelector('.cb_admin-table');

    // Should show Alice, Bob, Carol, Ricardo
    await expect(page.locator('.cb_admin-table')).toContainText('Alice McGregor');
    await expect(page.locator('.cb_admin-table')).toContainText('Bob Fraser');
    await expect(page.locator('.cb_admin-table')).toContainText('Carol Stewart');
    await expect(page.locator('.cb_admin-table')).toContainText('Ricardo Alvarado');
  });

  test('RBAC permission matrix is displayed', async ({ page }) => {
    await loginAs(page, 'L3-admin');
    await page.goto('/admin');

    // The admin page should show the RBAC matrix
    await expect(page.getByRole('heading', { name: 'RBAC Permission Matrix' })).toBeVisible();
  });

  test('L2 navigating to admin sees access denied', async ({ page }) => {
    await loginAs(page, 'L2-engineer');
    await page.goto('/admin');

    await expect(page.locator('text=Access Denied')).toBeVisible();
  });
});
