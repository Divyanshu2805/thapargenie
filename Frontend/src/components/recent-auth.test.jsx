import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  user: null,
  reauthenticateWithPopup: vi.fn(),
  reauthenticateWithCredential: vi.fn(),
}));
vi.mock('firebase/auth', () => ({
  EmailAuthProvider: { credential: (email, password) => ({ email, password }) },
  reauthenticateWithPopup: mocks.reauthenticateWithPopup,
  reauthenticateWithCredential: mocks.reauthenticateWithCredential,
}));
vi.mock('@/config/firebase', () => ({
  get firebaseAuth() {
    return { currentUser: mocks.user };
  },
  googleAuthProvider: {},
}));
vi.mock('@/utils/auth', () => ({ authErrorMessage: (error) => error.message }));

import { RecentAuthProvider, useRecentAuth } from './recent-auth';

const captured = { run: null };
function Capture() {
  const withRecentAuth = useRecentAuth();
  useEffect(() => {
    captured.run = withRecentAuth;
  });
  return null;
}
const run = (action) => captured.run(action);

const recentAuthError = () => Object.assign(new Error('Recent sign-in required.'), { code: 'recent_auth_required' });

describe('withRecentAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.user = { email: 'admin@thapar.edu', providerData: [{ providerId: 'password' }], getIdToken: vi.fn() };
    render(
      <RecentAuthProvider>
        <Capture />
      </RecentAuthProvider>,
    );
  });

  it('passes through when the action succeeds', async () => {
    await expect(run(async () => 'ok')).resolves.toBe('ok');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('asks for the password, refreshes the token and retries once', async () => {
    const action = vi.fn().mockRejectedValueOnce(recentAuthError()).mockResolvedValueOnce('deleted');
    let result;
    act(() => {
      result = run(action);
    });

    fireEvent.change(await screen.findByLabelText('Password'), { target: { value: 'secret1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await expect(result).resolves.toBe('deleted');
    expect(mocks.reauthenticateWithCredential).toHaveBeenCalledWith(mocks.user, { email: 'admin@thapar.edu', password: 'secret1' });
    expect(mocks.user.getIdToken).toHaveBeenCalledWith(true);
    expect(action).toHaveBeenCalledTimes(2);
  });

  it('rejects as cancelled when the admin closes the dialog', async () => {
    let result;
    act(() => {
      result = run(() => Promise.reject(recentAuthError()));
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
    await expect(result).rejects.toMatchObject({ code: 'request_cancelled' });
  });

  it('uses the Google popup for Google accounts', async () => {
    mocks.user.providerData = [{ providerId: 'google.com' }];
    const action = vi.fn().mockRejectedValueOnce(recentAuthError()).mockResolvedValueOnce('ok');
    let result;
    act(() => {
      result = run(action);
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Continue with Google' }));
    await expect(result).resolves.toBe('ok');
    await waitFor(() => expect(mocks.reauthenticateWithPopup).toHaveBeenCalled());
  });
});
