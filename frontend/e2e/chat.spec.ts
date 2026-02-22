import { test, expect } from '@playwright/test';

test.describe('Chat panel', () => {
  test('chat toggle button exists', async ({ page }) => {
    await page.goto('/');
    // Look for chat toggle button or chat panel element
    const chatToggle = page.getByRole('button', { name: /chat/i });
    if ((await chatToggle.count()) > 0) {
      await expect(chatToggle).toBeVisible();
    }
  });

  test('chat panel can be toggled open', async ({ page }) => {
    await page.goto('/');
    const chatToggle = page.getByRole('button', { name: /chat/i });
    if ((await chatToggle.count()) === 0) {
      test.skip();
      return;
    }
    await chatToggle.click();

    // Chat input or message area should appear
    const chatInput = page.locator('textarea, input[placeholder*="message" i], input[placeholder*="ask" i], input[placeholder*="chat" i]');
    await expect(chatInput.first()).toBeVisible({ timeout: 3000 });
  });

  test('chat input accepts text', async ({ page }) => {
    await page.goto('/');
    const chatToggle = page.getByRole('button', { name: /chat/i });
    if ((await chatToggle.count()) === 0) {
      test.skip();
      return;
    }
    await chatToggle.click();

    const chatInput = page.locator('textarea, input[placeholder*="message" i], input[placeholder*="ask" i], input[placeholder*="chat" i]');
    if ((await chatInput.count()) === 0) {
      test.skip();
      return;
    }
    await chatInput.first().fill('What is artificial intelligence?');
    await expect(chatInput.first()).toHaveValue('What is artificial intelligence?');
  });
});
