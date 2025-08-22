import { expect, test } from '@playwright/test';

import { STUDENT, ask, signIn } from './helpers';

// The API runs the offline AI provider: answers quote the first source with a [1]
// citation and stream word by word.

test('a student asks, sees a cited and dated answer, rates it and follows up', async ({ page }) => {
  await signIn(page, STUDENT);
  await ask(page, 'What is the boys hostel fee?');

  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);
  const citation = page.getByRole('button', { name: 'Source 1: Hostel fee structure' });
  await expect(citation).toBeVisible();
  await expect(page.getByText(/Rs 1,20,000 per year/)).toBeVisible();
  // The freshness line from the seeded document's session and date.
  await expect(page.getByText(/^Based on session \d{4}-\d{2} sources · dated /)).toBeVisible();

  const good = page.getByRole('button', { name: 'Good answer' });
  await good.click();
  await expect(good).toHaveAttribute('aria-pressed', 'true');

  // Follow-ups only on request, then a chip asks its question.
  await page.getByRole('button', { name: 'Suggest follow-ups' }).click();
  const followUps = page.getByRole('group', { name: 'Suggested follow-ups' });
  await expect(followUps).toBeVisible();
  await followUps.getByRole('button', { name: 'Is the mess fee included?' }).click();
  await expect(page.getByText('Is the mess fee included?', { exact: true })).toBeVisible();
  // The second answer may cite another document (the admin test uploads one).
  await expect(page.getByRole('button', { name: /^Source 1: / })).toHaveCount(2);

  // Reloading keeps everything: the rating, and the conversation in the sidebar.
  await page.reload();
  await expect(page.getByRole('button', { name: 'Good answer' }).first()).toHaveAttribute('aria-pressed', 'true');

  // Search (Ctrl/⌘ K palette) finds words from the answer, not just the title.
  await page.keyboard.press('Control+k');
  await page.getByRole('combobox', { name: 'Search chats' }).fill('1,20,000');
  const result = page.getByRole('option', { name: /What is the boys hostel fee\?/ });
  await expect(result).toContainText('ThaparGenie:');
  await expect(result.locator('mark', { hasText: '1,20,000' })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('option')).toHaveCount(0);

  // A long title slides to show the rest on hover.
  const row = page.getByRole('navigation', { name: 'Conversations' }).getByRole('link').first();
  await row.hover();
  await expect(row.locator('.marquee__text')).toHaveCSS('transform', /matrix/);
});

test('a student can stop an answer while it streams', async ({ page }) => {
  await signIn(page, STUDENT);
  await ask(page, 'Tell me about the girls hostel fee');

  const stop = page.getByRole('button', { name: 'Stop answering' });
  await expect(stop).toBeVisible();
  await stop.click();
  await expect(page.getByText(/Stopped\./)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send question' })).toBeVisible();
});

test('a student is kept out of the admin area', async ({ page }) => {
  await signIn(page, STUDENT);
  await page.goto('/admin/');
  await expect(page).toHaveURL(/\/chat\/$/);
});
