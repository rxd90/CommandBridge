import { test, expect } from '@playwright/test';
import { loginAs } from './helpers';

test.describe('Actions page', () => {
  test('loads and displays action cards', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/actions');
    // Wait for actions to load
    await page.waitForSelector('.cb_action-card');
    const cards = page.locator('.cb_action-card');
    // Should have at least some action cards (15 total)
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('search filters actions by name', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/actions');
    await page.waitForSelector('.cb_action-card');

    const allCount = await page.locator('.cb_action-card').count();

    await page.locator('.cb_kb-search input').fill('Pull');
    // Wait for filtering to apply
    await page.waitForTimeout(300);

    const filteredCount = await page.locator('.cb_action-card').count();
    expect(filteredCount).toBeLessThan(allCount);
    expect(filteredCount).toBeGreaterThan(0);
  });

  test('category chips filter actions', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/actions');
    await page.waitForSelector('.cb_action-card');

    const allCount = await page.locator('.cb_action-card').count();

    // Click a category chip
    const chip = page.locator('.cb_kb-category-chip').first();
    await chip.click();
    await page.waitForTimeout(300);

    const filteredCount = await page.locator('.cb_action-card').count();
    expect(filteredCount).toBeLessThanOrEqual(allCount);

    // Click again to deselect
    await chip.click();
    await page.waitForTimeout(300);
    const resetCount = await page.locator('.cb_action-card').count();
    expect(resetCount).toBe(allCount);
  });

  test('L1 sees Run buttons for low-risk and Request for high-risk', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/actions');
    await page.waitForSelector('.cb_action-card');

    // Should have at least one Run button and one Request button
    const runButtons = page.locator('.cb_action-card button', { hasText: 'Run' });
    const requestButtons = page.locator('.cb_action-card button', { hasText: 'Request' });
    expect(await runButtons.count()).toBeGreaterThan(0);
    expect(await requestButtons.count()).toBeGreaterThan(0);
  });

  test('execute modal opens and validates input', async ({ page }) => {
    await loginAs(page, 'L1-operator');
    await page.goto('/actions');
    await page.waitForSelector('.cb_action-card');

    // Click the first Run button
    const runButton = page.locator('.cb_action-card button', { hasText: 'Run' }).first();
    await runButton.click();

    // Modal should open
    await expect(page.locator('.cb_modal')).toBeVisible();

    // Try to submit without filling fields
    await page.locator('.cb_modal__actions button', { hasText: /Execute|Submit/ }).click();
    // Should show validation error in the result area
    await expect(page.locator('.cb_modal__result')).toContainText('required');
  });
});
