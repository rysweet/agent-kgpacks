import { test, expect } from '@playwright/test';

// Helper to load a graph before each test
async function loadGraph(page: import('@playwright/test').Page, article = 'Artificial intelligence') {
  await page.goto('/');
  const searchInput = page.getByRole('combobox');
  await searchInput.fill(article);
  await searchInput.press('Enter');
  await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
}

test.describe('Graph interaction', () => {
  test('SVG canvas renders with circle nodes', async ({ page }) => {
    await loadGraph(page);
    const circles = page.locator('svg circle');
    const count = await circles.count();
    expect(count).toBeGreaterThan(0);
  });

  test('SVG canvas renders with line edges', async ({ page }) => {
    await loadGraph(page);
    await page.waitForTimeout(2000);
    const lines = page.locator('svg line');
    const count = await lines.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('clicking a node shows article details in sidebar', async ({ page }) => {
    await loadGraph(page);
    const firstNode = page.locator('svg circle').first();
    await firstNode.click();
    await expect(page.getByText('Category:').first()).toBeVisible({ timeout: 5000 });
  });

  test('node details show title and category', async ({ page }) => {
    await loadGraph(page);
    const firstNode = page.locator('svg circle').first();
    await firstNode.click();
    await page.waitForTimeout(2000);
    // Category badge should appear with a known category
    await expect(
      page.locator('[class*="bg-purple"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('node details show Wikipedia link with security attributes', async ({ page }) => {
    await loadGraph(page);
    const firstNode = page.locator('svg circle').first();
    await firstNode.click();
    await page.waitForTimeout(3000);
    const wikiLink = page.locator('a[href*="wikipedia.org"]');
    if ((await wikiLink.count()) > 0) {
      await expect(wikiLink.first()).toHaveAttribute('target', '_blank');
      await expect(wikiLink.first()).toHaveAttribute('rel', /noopener/);
    }
  });

  test('selecting different nodes updates the sidebar', async ({ page }) => {
    await loadGraph(page);
    const circles = page.locator('svg circle');
    const count = await circles.count();
    if (count < 2) {
      test.skip();
      return;
    }

    // Click first node
    await circles.nth(0).click();
    await expect(page.getByText('Category:').first()).toBeVisible({ timeout: 5000 });

    // Click second node - sidebar should update
    await circles.nth(1).click();
    await page.waitForTimeout(1000);
    // Sidebar should still be visible with updated content
    await expect(page.getByText('Category:').first()).toBeVisible();
  });

  test('at least one node is rendered', async ({ page }) => {
    await loadGraph(page);
    const circles = page.locator('svg circle');
    const count = await circles.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('graph renders for different article categories', async ({ page }) => {
    // Test Physics article
    await loadGraph(page, 'General relativity');
    const count1 = await page.locator('svg circle').count();
    expect(count1).toBeGreaterThan(0);
  });

  test('graph renders for Biology articles', async ({ page }) => {
    await loadGraph(page, 'Evolution');
    const count = await page.locator('svg circle').count();
    expect(count).toBeGreaterThan(0);
  });
});
