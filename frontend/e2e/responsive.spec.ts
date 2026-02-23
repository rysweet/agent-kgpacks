import { test, expect } from '@playwright/test';

test.describe('Responsive layout', () => {
  test('sidebar is visible at desktop width', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');
    // Sidebar should be visible (contains "Filters" heading)
    await expect(page.getByText('Filters')).toBeVisible();
  });

  test('app renders at narrow mobile width without crashing', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    // Search bar should still be visible
    await expect(page.getByRole('combobox')).toBeVisible();
    // App title visible
    await expect(page.getByText('WikiGR')).toBeVisible();
  });

  test('app renders at tablet width', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await expect(page.getByRole('combobox')).toBeVisible();
  });

  test('search works at narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    // Graph should still load
    await expect(page.locator('svg')).toBeVisible({ timeout: 15000 });
  });

  test('chat panel works at narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    const chatButton = page.getByRole('button', { name: 'Open chat' });
    await chatButton.click();
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();
  });

  test('viewport resize does not crash the app', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });

    // Resize to mobile
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(1000);

    // Resize back to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForTimeout(1000);

    // Graph should still be visible
    await expect(page.locator('svg circle').first()).toBeVisible();
  });
});
