import { expect, test } from '@playwright/test';

const projectId = 'demo-thapargpt';
const emulatorUrl = 'http://127.0.0.1:9099';

async function latestVerificationCode(request, email) {
  await expect.poll(async () => {
    const response = await request.get(`${emulatorUrl}/emulator/v1/projects/${projectId}/oobCodes`);
    if (!response.ok()) return null;
    const payload = await response.json();
    const codes = payload.oobCodes || [];
    return codes.find((item) => item.email === email && item.requestType === 'VERIFY_EMAIL') || null;
  }).not.toBeNull();

  const response = await request.get(`${emulatorUrl}/emulator/v1/projects/${projectId}/oobCodes`);
  const payload = await response.json();
  const action = [...(payload.oobCodes || [])]
    .reverse()
    .find((item) => item.email === email && item.requestType === 'VERIFY_EMAIL');
  return action.oobCode;
}

test('signup, verify, remembered login, me profile, and cross-tab logout', async ({ browser, request }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const email = `stage04-${Date.now()}@example.invalid`;
  const password = 'Stage04-password';

  await page.goto('/register/');
  await page.getByLabel('Full name').fill('Stage Zero Four');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Confirm password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Verify your email' })).toBeVisible();

  const code = await latestVerificationCode(request, email);
  await page.goto(`/auth/action?mode=verifyEmail&oobCode=${encodeURIComponent(code)}`);
  await expect(page.getByText(/email action is complete/i)).toBeVisible();

  await page.goto('/logout/');
  await expect(page).toHaveURL(/\/login\/$/);
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByLabel('Remember me').check();
  const meResponse = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/me/') && response.request().method() === 'GET',
  );
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await meResponse).status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Approval pending' })).toBeVisible();

  const secondTab = await context.newPage();
  await secondTab.goto('/chat/deep-link?from=e2e');
  await expect(secondTab.getByRole('heading', { name: 'Approval pending' })).toBeVisible();

  await page.goto('/logout/');
  await expect(secondTab).toHaveURL(/\/login\/$/);
  await context.close();
});
