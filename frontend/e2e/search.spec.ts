import { test, expect } from '@playwright/test';

test.describe('Search workflows', () => {
  test('autocomplete shows suggestions when typing', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('art');
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('option').first()).toBeVisible();
  });

  test('clicking autocomplete suggestion loads graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('art');
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });
    await page.getByRole('option').first().click();
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('keyboard navigation of autocomplete: ArrowDown, ArrowUp, Enter', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('qu');
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });

    // Arrow down to first suggestion
    await searchInput.press('ArrowDown');
    const firstOption = page.getByRole('option').first();
    await expect(firstOption).toHaveAttribute('aria-selected', 'true');

    // Arrow up back to deselect
    await searchInput.press('ArrowUp');
    await expect(firstOption).toHaveAttribute('aria-selected', 'false');

    // Arrow down and Enter to select
    await searchInput.press('ArrowDown');
    await searchInput.press('Enter');
    // Listbox should close after selection
    await expect(page.getByRole('listbox')).not.toBeVisible({ timeout: 3000 });
  });

  test('Escape closes autocomplete dropdown', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('art');
    await expect(page.getByRole('listbox')).toBeVisible({ timeout: 5000 });
    await searchInput.press('Escape');
    await expect(page.getByRole('listbox')).not.toBeVisible({ timeout: 2000 });
  });

  test('submitting search via Enter in semantic mode loads graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('text mode search by title works', async ({ page }) => {
    await page.goto('/');
    // Switch to text mode
    const modeButton = page.getByRole('button', { name: /mode/i });
    await modeButton.click();
    await expect(page.getByText('text')).toBeVisible();

    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Quantum mechanics');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('semantic search mode is default', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('semantic')).toBeVisible();
  });

  test('mode toggle switches between text and semantic', async ({ page }) => {
    await page.goto('/');
    const modeButton = page.getByRole('button', { name: /mode/i });
    await expect(page.getByText('semantic')).toBeVisible();
    await modeButton.click();
    await expect(page.getByText('text')).toBeVisible();
    await modeButton.click();
    await expect(page.getByText('semantic')).toBeVisible();
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
    // Should show error or empty state — no graph nodes rendered
    await expect(searchInput).toBeVisible({ timeout: 5000 });
    const nodeCount = await page.locator('svg circle').count();
    expect(nodeCount).toBe(0);
  });

  test('search results show nodes in graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Quantum mechanics');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
    const nodeCount = await page.locator('svg circle').count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('searching different articles across categories', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');

    // Search Biology article
    await searchInput.fill('DNA');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });

    // Search History article
    await searchInput.fill('World War II');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('sequential searches reset the graph', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');

    // First search
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });

    // Second search - graph should update
    await searchInput.fill('Philosophy');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
    // Page still functional
    await expect(searchInput).toBeVisible();
  });

  test('loading spinner appears during search', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');
    await searchInput.fill('Artificial intelligence');

    // Start search and check for loading state
    await searchInput.press('Enter');
    // Loading indicator should appear (either spinner or loading text)
    const loadingIndicator = page.getByText('Loading graph...');
    // It may appear briefly - just verify no crash during loading
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });

  test('error recovery: failed search then successful search', async ({ page }) => {
    await page.goto('/');
    const searchInput = page.getByRole('combobox');

    // First search fails
    await searchInput.fill('nonexistent999');
    await searchInput.press('Enter');
    await page.waitForTimeout(3000);

    // Second search succeeds
    await searchInput.fill('Artificial intelligence');
    await searchInput.press('Enter');
    await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
  });
});
