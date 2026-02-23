import { test, expect } from '@playwright/test';

test.describe('PWA basics', () => {
  test('app has a title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/WikiGR/i);
  });

  test('app has meta viewport tag for mobile', async ({ page }) => {
    await page.goto('/');
    const viewport = page.locator('meta[name="viewport"]');
    await expect(viewport).toHaveAttribute('content', /width=device-width/);
  });

  test('app serves valid HTML document', async ({ page }) => {
    await page.goto('/');
    // HTML lang attribute present
    const html = page.locator('html');
    await expect(html).toHaveAttribute('lang', /en/);
  });

  test('manifest link is present with valid href', async ({ page }) => {
    await page.goto('/');
    const manifest = page.locator('link[rel="manifest"]');
    await expect(manifest).toHaveCount(1);
    const href = await manifest.getAttribute('href');
    expect(href).toBeTruthy();
  });

  test('app loads without JavaScript errors', async ({ page }) => {
    const jsErrors: string[] = [];
    page.on('pageerror', (error) => {
      jsErrors.push(error.message);
    });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    expect(jsErrors).toHaveLength(0);
  });
});
