import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  resendVerificationEmail: vi.fn(),
}));

vi.mock('../../utils/auth', () => ({
  authErrorMessage: (error) => error.message,
  logout: mocks.logout,
  resendVerificationEmail: mocks.resendVerificationEmail,
}));

import AccountStatus from './AccountStatus';

describe('account onboarding states', () => {
  beforeEach(() => vi.clearAllMocks());

  it('distinguishes unverified email and supports resend', async () => {
    mocks.resendVerificationEmail.mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <AccountStatus
          onRetry={vi.fn()}
          profile={{ email: 'student@example.edu', onboarding_status: 'email_verification_required' }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Verify your email' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }));
    await waitFor(() => expect(mocks.resendVerificationEmail).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('status')).toHaveTextContent('new verification email');
  });

  it('renders a separate ineligible state', () => {
    render(
      <MemoryRouter>
        <AccountStatus
          onRetry={vi.fn()}
          profile={{ email: 'student@example.edu', onboarding_status: 'access_denied' }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Account not eligible' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resend verification email' })).not.toBeInTheDocument();
  });
});
