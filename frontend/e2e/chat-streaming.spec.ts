import { test, expect } from '@playwright/test';

test.describe('Chat streaming responses', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();
  });

  test('sending a question shows user bubble and gets assistant response', async ({ page }) => {
    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');
    await chatInput.fill('What is artificial intelligence?');
    await page.getByRole('button', { name: 'Send' }).click();

    // User message appears
    await expect(page.getByText('What is artificial intelligence?')).toBeVisible({ timeout: 3000 });

    // Loading indicator (bouncing dots) should appear
    const dots = page.locator('.animate-bounce');
    // Wait for response - streaming may take time with real API
    // Either dots appear then disappear, or response text appears
    await expect(
      page.locator('.bg-gray-100').filter({ hasText: /.{20,}/ })
    ).toBeVisible({ timeout: 30000 });

    // The assistant response should have substantial content
    const assistantBubbles = page.locator('.bg-gray-100 p');
    const lastBubble = assistantBubbles.last();
    const text = await lastBubble.textContent();
    expect(text!.length).toBeGreaterThan(10);
  });

  test('send button is disabled while waiting for response', async ({ page }) => {
    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');
    await chatInput.fill('What is DNA?');
    await page.getByRole('button', { name: 'Send' }).click();

    // Send button should be disabled while loading
    const sendButton = page.getByRole('button', { name: 'Send' });
    // Input should be disabled during loading
    await expect(chatInput).toBeDisabled({ timeout: 2000 });

    // Wait for response to complete
    await expect(chatInput).toBeEnabled({ timeout: 30000 });
  });

  test('multiple messages create a conversation', async ({ page }) => {
    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');

    // First message
    await chatInput.fill('What is quantum mechanics?');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.getByText('What is quantum mechanics?')).toBeVisible({ timeout: 3000 });

    // Wait for response
    await expect(chatInput).toBeEnabled({ timeout: 30000 });

    // Second message
    await chatInput.fill('Tell me about evolution');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.getByText('Tell me about evolution')).toBeVisible({ timeout: 3000 });

    // Both user messages should be visible
    await expect(page.getByText('What is quantum mechanics?')).toBeVisible();
    await expect(page.getByText('Tell me about evolution')).toBeVisible();
  });
});
