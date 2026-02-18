/**
 * Shared helpers for CommandBridge Playwright E2E tests.
 */
import { type Page, expect } from '@playwright/test';

export type RoleName = 'L1-operator' | 'L2-engineer' | 'L3-admin';

/** Map role to user name from rbac/users.json. */
const ROLE_USERS: Record<RoleName, string> = {
  'L1-operator': 'Alice McGregor',
  'L2-engineer': 'Carol Stewart',
  'L3-admin': 'Ricardo Alvarado',
};

/**
 * Log in as the given role by clicking the matching user button on the
 * local-dev login page, then wait for redirect to home.
 */
export async function loginAs(page: Page, role: RoleName): Promise<void> {
  await page.goto('/login');
  await page.waitForSelector('.cb_login__user-list');
  const userName = ROLE_USERS[role];
  await page.locator('.cb_login__user-btn', { hasText: userName }).click();
  // localDevLogin sets sessionStorage and does window.location.href = '/'
  await page.waitForURL('/');
  // Wait for nav to render
  await page.waitForSelector('.cb_nav');
}
