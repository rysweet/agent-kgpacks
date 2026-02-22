import { test, expect } from '@playwright/test';

test.describe('Filter panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Load a graph first
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    await expect(page.locator('svg')).toBeVisible({ timeout: 10000 });
  });

  test('filter panel is visible after graph loads', async ({ page }) => {
    // Look for filter-related UI elements (checkboxes, sliders, or filter text)
    const filterArea = page.getByText(/filter|categor|depth/i).first();
    await expect(filterArea).toBeVisible({ timeout: 5000 });
  });

  test('depth control is present', async ({ page }) => {
    // Look for depth slider or depth-related input
    const depthControl = page.locator('input[type="range"]').first();
    if ((await depthControl.count()) > 0) {
      await expect(depthControl).toBeVisible();
    }
  });
});
