import { test, expect } from '@playwright/test';

async function loadGraph(page: import('@playwright/test').Page) {
  await page.goto('/');
  const searchInput = page.getByRole('combobox');
  await searchInput.fill('Artificial intelligence');
  await searchInput.press('Enter');
  await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
}

test.describe('Filter panel', () => {
  test('filter panel is visible after graph loads', async ({ page }) => {
    await loadGraph(page);
    await expect(page.getByText('Filters')).toBeVisible({ timeout: 5000 });
  });

  test('category checkboxes appear after graph loads', async ({ page }) => {
    await loadGraph(page);
    await expect(page.locator('label').filter({ hasText: 'Categories' })).toBeVisible();
    const checkboxes = page.locator('input[type="checkbox"]');
    const count = await checkboxes.count();
    // At least Select All + 1 category
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('Select All checkbox works', async ({ page }) => {
    await loadGraph(page);
    const selectAll = page.getByText('Select All');
    await expect(selectAll).toBeVisible();
    // Click Select All
    await selectAll.click();
    // Should show "N selected" text
    await expect(page.getByText(/selected/)).toBeVisible({ timeout: 2000 });
  });

  test('clicking Select All then a category shows selected count', async ({ page }) => {
    await loadGraph(page);
    // Click Select All to select all categories
    await page.getByText('Select All').click();
    // Should show "N selected" text
    await expect(page.getByText(/selected/)).toBeVisible({ timeout: 3000 });
  });

  test('depth slider is present and functional', async ({ page }) => {
    await loadGraph(page);
    const depthSlider = page.locator('input[type="range"]');
    await expect(depthSlider).toBeVisible();

    // Default value should be 2
    await expect(depthSlider).toHaveValue('2');

    // Change to 1
    await depthSlider.fill('1');
    await expect(page.getByTestId('depth-value')).toHaveText('1');

    // Change to 3
    await depthSlider.fill('3');
    await expect(page.getByTestId('depth-value')).toHaveText('3');
  });

  test('reset button clears filters', async ({ page }) => {
    await loadGraph(page);

    // Select all categories first
    await page.getByText('Select All').click();
    await expect(page.getByText(/selected/)).toBeVisible({ timeout: 3000 });

    // Click reset
    const resetButton = page.getByRole('button', { name: 'Reset filters' });
    await resetButton.click();

    // "N selected" should disappear
    await expect(page.getByText(/selected/)).not.toBeVisible({ timeout: 2000 });
  });

  test('collapse/expand toggle works', async ({ page }) => {
    await loadGraph(page);
    await expect(page.locator('label').filter({ hasText: 'Categories' })).toBeVisible();

    // Click collapse button
    const collapseButton = page.getByRole('button', { name: 'Collapse' });
    await collapseButton.click();

    // Categories label should be hidden
    await expect(page.locator('label').filter({ hasText: 'Categories' })).not.toBeVisible();

    // Click expand
    const expandButton = page.getByRole('button', { name: 'Expand' });
    await expandButton.click();

    // Categories should be visible again
    await expect(page.locator('label').filter({ hasText: 'Categories' })).toBeVisible();
  });
});
