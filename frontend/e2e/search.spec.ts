import { test, expect } from '@playwright/test';

test.describe('Search workflows', () => {
  test('autocomplete shows suggestions when typing', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('art');
    // Wait for debounce + API response
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });
    // Should show "Artificial intelligence" as a suggestion
    await expect(page.getByRole('option').first()).toBeVisible();
  });

  test('clicking autocomplete suggestion loads graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('art');
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });

    // Click the first suggestion
    await page.getByRole('option').first().click();

    // Graph should load - look for SVG with nodes
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('submitting search via Enter loads graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');

    // Wait for graph to load - SVG with circles
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('semantic search mode is default', async ({ page }) => {
    await page.goto('/');
    // Mode should show "semantic" by default
    await expect(page.getByText('semantic')).toBeVisible();
  });

  test('mode toggle switches between text and semantic', async ({ page }) => {
    await page.goto('/');
    const modeButton = page.getByRole('button', { name: /mode/i });
    await expect(page.getByText('semantic')).toBeVisible();
    await modeButton.click();
    await expect(page.getByText('text')).toBeVisible();
  });

  test('clear button resets search input', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('test query');

    const clearButton = page.getByRole('button', { name: 'Clear' });
    await expect(clearButton).toBeVisible();
    await clearButton.click();

    await expect(searchInput).toHaveValue('');
  });

  test('searching nonexistent article shows error gracefully', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('xyznonexistent12345');
    await searchInput.press('Enter');

    // Should either show error or stay on empty state - not crash
    await page.waitForTimeout(3000);
    await expect(searchInput).toBeVisible();
  });

  test('search results show nodes in graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Quantum mechanics');
    await searchInput.press('Enter');

    // Graph should render nodes
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
    const nodeCount = await page.locator('svg circle').count();
    expect(nodeCount).toBeGreaterThan(0);
  });
});
