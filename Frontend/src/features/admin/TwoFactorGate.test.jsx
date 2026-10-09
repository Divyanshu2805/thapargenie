import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  adminKeys: { twoFactor: ['admin', 'two-factor'] },
  getTwoFactorStatus: vi.fn(),
  setUpTwoFactor: vi.fn(),
  confirmTwoFactor: vi.fn(),
  verifyTwoFactor: vi.fn(),
  newRecoveryCodes: vi.fn(),
}));
vi.mock('@/lib/api/admin', () => api);
vi.mock('@/components/recent-auth', () => ({ useRecentAuth: () => (action) => action() }));

import TwoFactorGate, { gateStep, groupKey, isTwoFactorError } from './TwoFactorGate';

const status = (overrides) => ({ required: true, enrolled: true, verified: true, recovery_codes_left: 10, session_hours: 12, ...overrides });

function renderGate() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TwoFactorGate>
        <h1>Admin dashboard</h1>
      </TwoFactorGate>
    </QueryClientProvider>,
  );
  return client;
}

describe('two-factor helpers', () => {
  it('picks the screen from the status', () => {
    expect(gateStep(status())).toBe('open');
    expect(gateStep(status({ verified: false }))).toBe('verify');
    expect(gateStep(status({ enrolled: false, verified: false }))).toBe('enrol');
    expect(gateStep(status({ required: false, enrolled: false, verified: false }))).toBe('open');
  });

  it('groups the key and recognises the API’s two-factor refusals', () => {
    expect(groupKey('ABCDEFGHIJ')).toBe('ABCD EFGH IJ');
    expect(isTwoFactorError({ code: 'second_factor_required' })).toBe(true);
    expect(isTwoFactorError({ code: 'second_factor_setup_required' })).toBe(true);
    expect(isTwoFactorError({ code: 'recent_auth_required' })).toBe(false);
  });
});

describe('TwoFactorGate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the dashboard once this sign-in has passed', async () => {
    api.getTwoFactorStatus.mockResolvedValue(status());
    renderGate();
    expect(await screen.findByRole('heading', { name: 'Admin dashboard' })).toBeInTheDocument();
  });

  it('asks for a code and opens the dashboard when it is right', async () => {
    api.getTwoFactorStatus.mockResolvedValue(status({ verified: false }));
    api.verifyTwoFactor.mockRejectedValueOnce(Object.assign(new Error('That code is not right.'), { code: 'second_factor_invalid_code' }));
    api.verifyTwoFactor.mockResolvedValueOnce(status());
    renderGate();

    const field = await screen.findByLabelText('6-digit code');
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).not.toBeInTheDocument();
    fireEvent.change(field, { target: { value: '111111' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('That code is not right.');

    fireEvent.change(field, { target: { value: ' 123456 ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByRole('heading', { name: 'Admin dashboard' })).toBeInTheDocument();
    expect(api.verifyTwoFactor).toHaveBeenLastCalledWith({ code: '123456' });
  });

  it('takes a backup code instead', async () => {
    api.getTwoFactorStatus.mockResolvedValue(status({ verified: false, recovery_codes_left: 1 }));
    api.verifyTwoFactor.mockResolvedValue(status({ recovery_codes_left: 0 }));
    renderGate();

    fireEvent.click(await screen.findByRole('button', { name: /use a backup code/i }));
    expect(screen.getByText(/1 backup code is left/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Backup code'), { target: { value: 'abcd-efgh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => expect(api.verifyTwoFactor).toHaveBeenCalledWith({ recovery_code: 'abcd-efgh' }));
  });

  it('walks a new admin through setup and shows the backup codes once', async () => {
    api.getTwoFactorStatus.mockResolvedValue(status({ enrolled: false, verified: false }));
    api.setUpTwoFactor.mockResolvedValue({ secret: 'ABCDEFGH', otpauth_uri: 'otpauth://totp/ThaparGenie:a%40thapar.edu?secret=ABCDEFGH' });
    api.confirmTwoFactor.mockResolvedValue({ recovery_codes: ['AAAA-BBBB', 'CCCC-DDDD'], status: status() });
    renderGate();

    expect(await screen.findByRole('img', { name: /QR code/ })).toBeInTheDocument();
    expect(screen.getByText('ABCD EFGH')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Turn on two-factor' }));

    expect(await screen.findByRole('heading', { name: 'Save your backup codes' })).toBeInTheDocument();
    expect(screen.getByText('AAAA-BBBB')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'I’ve saved them' }));
    expect(screen.getByRole('heading', { name: 'Admin dashboard' })).toBeInTheDocument();
    expect(screen.queryByText('AAAA-BBBB')).not.toBeInTheDocument();
  });

  it('asks again when an admin request is refused because the check ran out', async () => {
    api.getTwoFactorStatus.mockResolvedValueOnce(status()).mockResolvedValue(status({ verified: false }));
    const client = renderGate();
    await screen.findByRole('heading', { name: 'Admin dashboard' });

    const refused = Object.assign(new Error('Enter the code from your authenticator app.'), { code: 'second_factor_required' });
    await client.fetchQuery({ queryKey: ['admin', 'users', {}], queryFn: () => Promise.reject(refused) }).catch(() => {});
    expect(await screen.findByLabelText('6-digit code')).toBeInTheDocument();
  });
});
