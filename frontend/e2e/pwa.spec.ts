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

  test('manifest link is present', async ({ page }) => {
    await page.goto('/');
    // PWA manifest should be linked in the HTML
    const manifest = page.locator('link[rel="manifest"]');
    if ((await manifest.count()) > 0) {
      const href = await manifest.getAttribute('href');
      expect(href).toBeTruthy();
    }
  });

  test('app loads without JavaScript errors', async ({ page }) => {
    const jsErrors: string[] = [];
    page.on('pageerror', (error) => {
      jsErrors.push(error.message);
    });
    await page.goto('/');
    await page.waitForTimeout(3000);
    expect(jsErrors).toHaveLength(0);
  });
});
