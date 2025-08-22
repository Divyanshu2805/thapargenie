import { Buffer } from 'node:buffer';

import { expect } from '@playwright/test';

// Accounts created by `manage.py seed_e2e` in the Firebase Auth emulator.
export const PASSWORD = 'E2e-only-password-1!';
export const STUDENT = 'e2e-student@example.com';
export const ADMIN = 'e2e-admin@example.com';

export async function signIn(page, email) {
  await page.goto('/login/');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/chat\/$/);
}

export async function ask(page, question) {
  await page.getByLabel('Ask a question about TIET').fill(question);
  await page.getByRole('button', { name: 'Send question' }).click();
}

/** A one-page PDF with a real text layer (one text line per entry in `lines`). */
export function makePdf(lines) {
  const escape = (text) => text.replace(/[\\()]/g, (char) => `\\${char}`);
  const content = ['BT', '/F1 11 Tf', '14 TL', '72 740 Td', ...lines.map((line) => `(${escape(line)}) Tj T*`), 'ET'].join('\n');
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let body = '%PDF-1.4\n';
  const offsets = objects.map((object, index) => {
    const offset = body.length;
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
    return offset;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('');
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, 'latin1');
}
