import { test, expect } from '@playwright/test';

test.describe('Chat panel', () => {
  test('chat button shows "Ask KG" label', async ({ page }) => {
    await page.goto('/');
    const chatButton = page.getByRole('button', { name: 'Open chat' });
    await expect(chatButton).toBeVisible();
    await expect(chatButton).toHaveText('Ask KG');
  });

  test('clicking chat button opens the panel', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();
    // Chat panel header should appear
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();
  });

  test('chat panel shows empty state message', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();
    await expect(
      page.getByText('Ask a question about the knowledge graph.')
    ).toBeVisible();
  });

  test('close button closes the panel', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();

    await page.getByRole('button', { name: 'Close chat' }).click();
    await expect(page.getByText('Knowledge Graph Chat')).not.toBeVisible();
    // "Ask KG" button should reappear
    await expect(page.getByRole('button', { name: 'Open chat' })).toBeVisible();
  });

  test('chat input accepts text', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();

    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');
    await expect(chatInput).toBeVisible();
    await chatInput.fill('What is artificial intelligence?');
    await expect(chatInput).toHaveValue('What is artificial intelligence?');
  });

  test('send button is disabled when input is empty', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();

    const sendButton = page.getByRole('button', { name: 'Send' });
    await expect(sendButton).toBeDisabled();
  });

  test('send button is enabled when input has text', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();

    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');
    await chatInput.fill('test question');

    const sendButton = page.getByRole('button', { name: 'Send' });
    await expect(sendButton).toBeEnabled();
  });

  test('submitting chat shows user message bubble', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open chat' }).click();

    const chatInput = page.getByPlaceholder('Ask about the knowledge graph...');
    await chatInput.fill('What is AI?');

    const sendButton = page.getByRole('button', { name: 'Send' });
    await sendButton.click();

    // User message should appear in the chat
    await expect(page.getByText('What is AI?')).toBeVisible({ timeout: 3000 });
    // Input should be cleared
    await expect(chatInput).toHaveValue('');
  });

  test('chat panel can be reopened after closing', async ({ page }) => {
    await page.goto('/');
    // Open
    await page.getByRole('button', { name: 'Open chat' }).click();
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();

    // Close
    await page.getByRole('button', { name: 'Close chat' }).click();

    // Reopen
    await page.getByRole('button', { name: 'Open chat' }).click();
    await expect(page.getByText('Knowledge Graph Chat')).toBeVisible();
  });
});
