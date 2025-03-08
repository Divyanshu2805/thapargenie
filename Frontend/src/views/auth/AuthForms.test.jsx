import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  loginWithGoogle: vi.fn(),
  register: vi.fn(),
  requestPasswordReset: vi.fn(),
}));

vi.mock('../../utils/auth', () => ({
  authErrorMessage: (error) => error.message,
  login: mocks.login,
  loginWithGoogle: mocks.loginWithGoogle,
  register: mocks.register,
  requestPasswordReset: mocks.requestPasswordReset,
}));

import ForgotPassword from './ForgotPassword/ForgotPassword';
import Login from './Login/Login';
import Register from './Register/Register';

function renderWithRouter(element, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="*" element={element} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('authentication forms', () => {
  beforeEach(() => vi.clearAllMocks());

  it('passes remember-me selection to email/password login', async () => {
    mocks.login.mockResolvedValue({});
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'student@example.edu' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret1' } });
    fireEvent.click(screen.getByLabelText('Remember me'));
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(mocks.login).toHaveBeenCalledWith('student@example.edu', 'secret1', true);
    });
  });

  it('keeps Google sign-in behind an explicit user click', async () => {
    mocks.loginWithGoogle.mockResolvedValue({});
    renderWithRouter(<Login />);

    expect(mocks.loginWithGoogle).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
    await waitFor(() => expect(mocks.loginWithGoogle).toHaveBeenCalledWith(false));
  });

  it('shows an inline signup error for mismatched passwords', () => {
    renderWithRouter(<Register />);

    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Student Name' } });
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'student@example.edu' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret1' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'secret2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(mocks.register).not.toHaveBeenCalled();
  });

  it('submits password-reset mail through Firebase and renders a deterministic success state', async () => {
    mocks.requestPasswordReset.mockResolvedValue(undefined);
    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'student@example.edu' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Check your inbox');
    expect(mocks.requestPasswordReset).toHaveBeenCalledWith('student@example.edu');
  });
});
