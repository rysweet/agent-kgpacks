import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/**
 * Load a graph by searching for an article and waiting for nodes to render.
 * Shared across E2E test suites.
 */
export async function loadGraph(page: Page, article = 'Artificial intelligence') {
  await page.goto('/');
  const searchInput = page.getByRole('combobox');
  await searchInput.fill(article);
  await searchInput.press('Enter');
  await expect(page.locator('svg circle').first()).toBeVisible({ timeout: 15000 });
}
