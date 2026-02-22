import { test, expect } from '@playwright/test';

test.describe('App loads', () => {
  test('renders without crashing', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/WikiGR/i);
  });

  test('search bar is visible and focusable', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByPlaceholder('Search articles...');
    await expect(searchInput).toBeVisible();
    await searchInput.focus();
    await expect(searchInput).toBeFocused();
  });

  test('search bar has combobox role', async ({ page }) => {
    await page.goto('/');
    const combobox = page.getByRole('combobox');
    await expect(combobox).toBeVisible();
  });

  test('mode toggle button exists', async ({ page }) => {
    await page.goto('/');
    // The mode toggle shows "text" or "semantic"
    const modeButton = page.getByRole('button', { name: /mode/i });
    await expect(modeButton).toBeVisible();
  });

  test('no console errors on load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    await page.goto('/');
    await page.waitForTimeout(2000);
    // Filter out expected errors (e.g., network errors when no graph is loaded)
    const unexpectedErrors = errors.filter(
      (e) => !e.includes('favicon') && !e.includes('net::ERR')
    );
    expect(unexpectedErrors).toHaveLength(0);
  });
});
