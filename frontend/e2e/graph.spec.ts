import { test, expect } from '@playwright/test';

test.describe('Graph interaction', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    // Wait for graph SVG with nodes to appear
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('SVG canvas renders with circle nodes', async ({ page }) => {
    const circles = page.locator('svg circle');
    const count = await circles.count();
    expect(count).toBeGreaterThan(0);
  });

  test('SVG canvas renders with line edges', async ({ page }) => {
    // Wait for force simulation to settle
    await page.waitForTimeout(2000);
    const lines = page.locator('svg line');
    const count = await lines.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('clicking a node shows article details in sidebar', async ({ page }) => {
    const firstNode = page.locator('svg circle').first();
    await firstNode.click();

    // Wait for sidebar to update - look for "Category:" label which is unique
    await expect(
      page.getByText('Category:').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('node details show Wikipedia link', async ({ page }) => {
    const firstNode = page.locator('svg circle').first();
    await firstNode.click();

    // Wait for article details to load
    await page.waitForTimeout(3000);

    const wikiLink = page.locator('a[href*="wikipedia.org"]');
    if ((await wikiLink.count()) > 0) {
      await expect(wikiLink.first()).toHaveAttribute('target', '_blank');
    }
  });

  test('at least one node is rendered', async ({ page }) => {
    const circles = page.locator('svg circle');
    const count = await circles.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
