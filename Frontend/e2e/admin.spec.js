import { expect, test } from '@playwright/test';

import { ADMIN, makePdf, signIn } from './helpers';

const NOTICE = [
  'Mess fee notice for all hostels.',
  'The mess fee for the academic session is Rs 45,000 per year, charged in two instalments.',
  'Students staying in the hostel must pay the first instalment before the start of the semester.',
  'Late payment attracts a fine of Rs 500 per week. Refunds follow the hostel office rules.',
];

test('an admin uploads a PDF that becomes ready, marks it not current in bulk and sees the audit trail', async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto('/admin/documents');

  await page.getByRole('button', { name: 'Add knowledge' }).click();
  const dialog = page.getByRole('dialog');
  // A line unique to this run, so a re-run against the same database is not a duplicate.
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'mess-notice.pdf',
    mimeType: 'application/pdf',
    buffer: makePdf([...NOTICE, `Reference ${Date.now()}.`]),
  });
  await dialog.getByRole('button', { name: 'Add to knowledge base' }).click();
  await expect(dialog).toBeHidden();

  // Processing runs in the background; the list polls while anything is in flight.
  const row = page.getByRole('row').filter({ hasText: 'mess-notice' });
  await expect(row).toBeVisible();
  await expect(row.getByText('Ready')).toBeVisible({ timeout: 45_000 });

  // Bulk edit, setting "current" off through its own "change" tick.
  await row.getByRole('checkbox', { name: 'Select mess-notice' }).check();
  const bar = page.getByRole('region', { name: 'Bulk actions' });
  await expect(bar).toContainText('1 selected');
  await bar.getByRole('button', { name: /Edit details/ }).click();
  const edit = page.getByRole('dialog');
  await edit.getByRole('switch', { name: 'Current information' }).click();
  await expect(edit.getByRole('checkbox', { name: 'Change current information' })).toBeChecked();
  await edit.getByRole('button', { name: 'Apply changes' }).click();
  await expect(page.getByText('Updated 1 document')).toBeVisible();
  await expect(row).toContainText('Superseded');

  await page.goto('/admin/audit-log');
  await expect(page.getByText('document · updated').first()).toBeVisible();
  await expect(page.getByText('document · created').first()).toBeVisible();
});
