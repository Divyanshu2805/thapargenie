import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  completeEmailVerification: vi.fn(),
  completePasswordReset: vi.fn(),
  inspectPasswordResetCode: vi.fn(),
}));

vi.mock('../../utils/auth', () => ({
  authErrorMessage: (error) => error.message,
  checkPassword: async (password) => (password.length < 6 ? 'Use at least 6 characters.' : ''),
  passwordRequirements: async () => 'Use at least 6 characters.',
  completeEmailVerification: mocks.completeEmailVerification,
  completePasswordReset: mocks.completePasswordReset,
  inspectPasswordResetCode: mocks.inspectPasswordResetCode,
}));

import AuthAction from './AuthAction';

describe('Firebase email action route', () => {
  beforeEach(() => vi.clearAllMocks());

  it('applies verification action codes', async () => {
    mocks.completeEmailVerification.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={['/auth/action?mode=verifyEmail&oobCode=verify-code']}>
        <AuthAction />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/email action is complete/i)).toBeInTheDocument();
    expect(mocks.completeEmailVerification).toHaveBeenCalledWith('verify-code');
  });

  it('validates and completes a password-reset action', async () => {
    mocks.inspectPasswordResetCode.mockResolvedValue('student@example.edu');
    mocks.completePasswordReset.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={['/auth/action?mode=resetPassword&oobCode=reset-code']}>
        <AuthAction />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/resetting the password for student@example.edu/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-secret' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'new-secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save new password' }));

    await waitFor(() => {
      expect(mocks.completePasswordReset).toHaveBeenCalledWith('reset-code', 'new-secret');
    });
    expect(await screen.findByText(/password has been changed/i)).toBeInTheDocument();
  });

  it('rejects legacy or incomplete action parameters', async () => {
    render(
      <MemoryRouter initialEntries={['/auth/action?otp=legacy&uuidb64=legacy']}>
        <AuthAction />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('incomplete or unsupported');
  });
});
