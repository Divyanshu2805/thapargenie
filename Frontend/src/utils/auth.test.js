import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  applyActionCode: vi.fn(),
  auth: { currentUser: null },
  browserLocalPersistence: { name: 'local' },
  browserSessionPersistence: { name: 'session' },
  clearUserSpecificState: vi.fn(),
  confirmPasswordReset: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  getIdToken: vi.fn(),
  reload: vi.fn(),
  sendEmailVerification: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  setPersistence: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  updateProfile: vi.fn(),
  validatePassword: vi.fn(),
  verifyPasswordResetCode: vi.fn(),
}));

vi.mock('firebase/auth', () => ({
  applyActionCode: mocks.applyActionCode,
  browserLocalPersistence: mocks.browserLocalPersistence,
  browserSessionPersistence: mocks.browserSessionPersistence,
  confirmPasswordReset: mocks.confirmPasswordReset,
  createUserWithEmailAndPassword: mocks.createUserWithEmailAndPassword,
  getIdToken: mocks.getIdToken,
  reload: mocks.reload,
  sendEmailVerification: mocks.sendEmailVerification,
  sendPasswordResetEmail: mocks.sendPasswordResetEmail,
  setPersistence: mocks.setPersistence,
  signInWithEmailAndPassword: mocks.signInWithEmailAndPassword,
  signInWithPopup: mocks.signInWithPopup,
  signOut: mocks.signOut,
  updateProfile: mocks.updateProfile,
  validatePassword: mocks.validatePassword,
  verifyPasswordResetCode: mocks.verifyPasswordResetCode,
}));

vi.mock('../config/firebase', () => ({
  googleAuthProvider: { providerId: 'google.com' },
  requireFirebaseAuth: () => mocks.auth,
}));

vi.mock('./session', () => ({ clearUserSpecificState: mocks.clearUserSpecificState }));

import {
  authErrorMessage,
  completeEmailVerification,
  completePasswordReset,
  inspectPasswordResetCode,
  login,
  loginWithGoogle,
  logout,
  register,
  requestPasswordReset,
} from './auth';

describe('Firebase authentication operations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.auth.currentUser = null;
  });

  it('keeps popup and environment failures actionable', () => {
    expect(authErrorMessage({ code: 'auth/popup-blocked' })).toContain('blocked');
    expect(authErrorMessage({ code: 'auth/operation-not-supported-in-this-environment' }))
      .toContain('cannot open');
    expect(authErrorMessage({ code: 'auth/unexpected-development-error' }))
      .toContain('auth/unexpected-development-error');
  });

  it('uses local persistence only when remember me is selected', async () => {
    await login(' student@example.edu ', 'secret1', true);

    expect(mocks.setPersistence).toHaveBeenCalledWith(mocks.auth, mocks.browserLocalPersistence);
    expect(mocks.signInWithEmailAndPassword).toHaveBeenCalledWith(
      mocks.auth,
      'student@example.edu',
      'secret1',
    );
  });

  it('uses session persistence at the Google popup boundary', async () => {
    await loginWithGoogle(false);

    expect(mocks.setPersistence).toHaveBeenCalledWith(mocks.auth, mocks.browserSessionPersistence);
    expect(mocks.signInWithPopup).toHaveBeenCalledWith(
      mocks.auth,
      expect.objectContaining({ providerId: 'google.com' }),
    );
  });

  it('rejects mismatched signup passwords before creating a Firebase user', async () => {
    await expect(register({
      displayName: 'Student',
      email: 'student@example.edu',
      password: 'secret1',
      passwordConfirmation: 'different',
    })).rejects.toMatchObject({ code: 'password_mismatch' });
    expect(mocks.createUserWithEmailAndPassword).not.toHaveBeenCalled();
  });

  it('creates a session-persistent account and sends verification mail', async () => {
    const user = {};
    mocks.createUserWithEmailAndPassword.mockResolvedValue({ user });

    await register({
      displayName: ' Student Name ',
      email: 'student@example.edu',
      password: 'secret1',
      passwordConfirmation: 'secret1',
    });

    expect(mocks.updateProfile).toHaveBeenCalledWith(user, { displayName: 'Student Name' });
    expect(mocks.sendEmailVerification).toHaveBeenCalledWith(
      user,
      expect.objectContaining({
        url: expect.stringMatching(/\/login\/$/),
        handleCodeInApp: false,
      }),
    );
  });

  it('uses Firebase for reset inspection and completion', async () => {
    await requestPasswordReset(' student@example.edu ');
    await inspectPasswordResetCode('reset-code');
    await completePasswordReset('reset-code', 'new-secret');

    expect(mocks.sendPasswordResetEmail).toHaveBeenCalledWith(
      mocks.auth,
      'student@example.edu',
      expect.objectContaining({
        url: expect.stringMatching(/\/login\/$/),
        handleCodeInApp: false,
      }),
    );
    expect(mocks.verifyPasswordResetCode).toHaveBeenCalledWith(mocks.auth, 'reset-code');
    expect(mocks.confirmPasswordReset).toHaveBeenCalledWith(mocks.auth, 'reset-code', 'new-secret');
  });

  it('refreshes the current user after email verification', async () => {
    const user = {};
    mocks.auth.currentUser = user;

    await completeEmailVerification('verify-code');

    expect(mocks.applyActionCode).toHaveBeenCalledWith(mocks.auth, 'verify-code');
    expect(mocks.reload).toHaveBeenCalledWith(user);
    expect(mocks.getIdToken).toHaveBeenCalledWith(user, true);
  });

  it('clears user data before signing out', async () => {
    await logout();

    expect(mocks.clearUserSpecificState).toHaveBeenCalledTimes(1);
    expect(mocks.signOut).toHaveBeenCalledWith(mocks.auth);
    expect(mocks.clearUserSpecificState.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.signOut.mock.invocationCallOrder[0],
    );
  });
});

describe('password policy', () => {
  const enforced = {
    enforcementState: 'ENFORCE',
    customStrengthOptions: { minPasswordLength: 8, containsUppercaseLetter: true, containsLowercaseLetter: true, containsNumericCharacter: true },
  };
  const status = (isValid, passwordPolicy = enforced) => ({ isValid, passwordPolicy });

  it('describes the enforced policy in words', async () => {
    const { passwordRequirements } = await import('./auth');
    mocks.validatePassword.mockResolvedValue(status(false));
    await expect(passwordRequirements()).resolves.toBe(
      'Use at least 8 characters, with an uppercase letter, a lowercase letter and a number.',
    );
  });

  it('rejects a password the enforced policy refuses and accepts one it allows', async () => {
    const { checkPassword } = await import('./auth');
    mocks.validatePassword.mockResolvedValueOnce(status(false));
    await expect(checkPassword('secret12')).resolves.toMatch(/^Use at least 8 characters/);
    mocks.validatePassword.mockResolvedValueOnce(status(true));
    await expect(checkPassword('Secret12')).resolves.toBe('');
  });

  it("ignores a policy that is not enforced, keeping Firebase's six-character minimum", async () => {
    const { checkPassword, passwordRequirements } = await import('./auth');
    const off = { ...enforced, enforcementState: 'OFF' };
    mocks.validatePassword.mockResolvedValue(status(false, off));
    await expect(passwordRequirements()).resolves.toBe('Use at least 6 characters.');
    await expect(checkPassword('secret')).resolves.toBe('');
    await expect(checkPassword('short')).resolves.toBe('Use at least 6 characters.');
  });

  it('falls back to the six-character minimum when the policy cannot be read', async () => {
    const { checkPassword, passwordRequirements } = await import('./auth');
    mocks.validatePassword.mockRejectedValue(new Error('offline'));
    await expect(passwordRequirements()).resolves.toBe('Use at least 6 characters.');
    await expect(checkPassword('short')).resolves.toBe('Use at least 6 characters.');
    await expect(checkPassword('longer1')).resolves.toBe('');
  });
});
