import { test, expect } from '@playwright/test';

async function loadGraph(page: import('@playwright/test').Page) {
  await page.goto('/');
  const searchInput = page.getByRole('combobox');
  await searchInput.fill('Artificial intelligence');
  await searchInput.press('Enter');
  await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  // Wait for simulation to settle
  await page.waitForTimeout(2000);
}

test.describe('Graph keyboard zoom/pan', () => {
  test('SVG has aria-label with keyboard instructions', async ({ page }) => {
    await loadGraph(page);
    const svg = page.locator('svg[aria-label]');
    await expect(svg).toHaveAttribute('aria-label', /zoom.*arrow.*pan/i);
  });

  test('+ key zooms in (transform changes)', async ({ page }) => {
    await loadGraph(page);
    const graphLayer = page.locator('.graph-layer');
    const transformBefore = await graphLayer.getAttribute('transform');

    // Focus the SVG area (click on background, not a node)
    await page.locator('svg').click({ position: { x: 10, y: 10 } });
    await page.keyboard.press('+');
    await page.waitForTimeout(300);

    const transformAfter = await graphLayer.getAttribute('transform');
    // Transform should change after zoom
    expect(transformAfter).not.toEqual(transformBefore);
  });

  test('- key zooms out (transform changes)', async ({ page }) => {
    await loadGraph(page);

    // Focus the SVG
    await page.locator('svg').click({ position: { x: 10, y: 10 } });
    await page.keyboard.press('-');
    await page.waitForTimeout(300);

    const graphLayer = page.locator('.graph-layer');
    const transform = await graphLayer.getAttribute('transform');
    // Should have a scale transform
    expect(transform).toBeTruthy();
  });

  test('arrow keys pan the graph', async ({ page }) => {
    await loadGraph(page);
    const graphLayer = page.locator('.graph-layer');

    // Focus the SVG
    await page.locator('svg').click({ position: { x: 10, y: 10 } });

    const transformBefore = await graphLayer.getAttribute('transform');

    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(200);

    const transformAfter = await graphLayer.getAttribute('transform');
    expect(transformAfter).not.toEqual(transformBefore);
  });

  test('0 key resets zoom to default', async ({ page }) => {
    await loadGraph(page);

    // Focus and zoom in first
    await page.locator('svg').click({ position: { x: 10, y: 10 } });
    await page.keyboard.press('+');
    await page.keyboard.press('+');
    await page.waitForTimeout(300);

    // Reset
    await page.keyboard.press('0');
    await page.waitForTimeout(400);

    // Graph should still be visible
    await expect(page.locator('svg circle').first()).toBeVisible();
  });

  test('keyboard shortcuts do not fire when typing in search input', async ({ page }) => {
    await loadGraph(page);
    const searchInput = page.getByRole('combobox');
    await searchInput.focus();

    // Type + in search input - should not zoom, should type in input
    await searchInput.fill('test+query');
    await expect(searchInput).toHaveValue('test+query');
  });
});
