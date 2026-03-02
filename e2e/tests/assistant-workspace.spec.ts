import { expect, test } from '@playwright/test';

async function login(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
  await page.getByLabel('Email').fill('test.user@exobrain.local');
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByRole('button', { name: 'Open user menu' })).toBeVisible();
}

test.describe('assistant frontend workspace (mock API)', () => {
  test('supports login, journal switching, chat scrolling, and logout', async ({ page }) => {
    await login(page);

    await expect(page.getByText('Journal:')).toBeVisible();

    const messagesContainer = page.locator('.messages');
    await expect(messagesContainer).toBeVisible();

    await page.getByRole('button', { name: 'Open journals' }).click();
    await expect(page.locator('.journal-item').nth(1)).toBeVisible();
    await page.locator('.journal-item').nth(1).click();

    await expect(page.getByLabel('Type your message')).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled();

    await page.getByRole('button', { name: /Today/ }).click();
    await expect(page.getByLabel('Type your message')).toBeEnabled();

    await page.getByLabel('Type your message').fill('Scroll check message');
    await page.getByRole('button', { name: 'Send message' }).click();

    await expect(page.getByText('Mock response: Scroll check message')).toBeVisible();

    const distanceFromBottom = await messagesContainer.evaluate((element) => {
      const node = element as HTMLDivElement;
      return node.scrollHeight - (node.scrollTop + node.clientHeight);
    });
    expect(distanceFromBottom).toBeLessThan(120);

    await page.getByRole('button', { name: 'Open user menu' }).click();
    await page.getByRole('button', { name: 'Logout' }).click();

    await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
  });

  test('renders multiline code blocks with preserved line breaks', async ({ page }) => {
    await login(page);

    const codeBlock = page.locator('.exo-md-code').first();
    const codePre = page.locator('.exo-md-code-pre').first();
    await expect(codeBlock).toContainText('const status = "ready";');
    await expect(codeBlock).toContainText('console.log(status);');

    const codeText = await codeBlock.innerText();
    expect(codeText).toContain('const status = "ready";\nconsole.log(status);');

    await expect(codePre).toHaveCSS('white-space', 'pre');
    await expect(page.locator('.exo-md-code-language').first()).toBeVisible();
  });
});
