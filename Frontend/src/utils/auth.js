import {
  applyActionCode,
  browserLocalPersistence,
  browserSessionPersistence,
  confirmPasswordReset,
  createUserWithEmailAndPassword,
  getIdToken,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  verifyPasswordResetCode,
} from 'firebase/auth';

import { googleAuthProvider, requireFirebaseAuth } from '../config/firebase';
import { clearUserSpecificState } from './session';

const hostedActionSettings = () => ({
  url: `${window.location.origin}/login/`,
  handleCodeInApp: false,
});

export function authErrorMessage(error) {
  const messages = {
    password_mismatch: 'Passwords do not match.',
    'auth/email-already-in-use': 'An account already uses this email address.',
    'auth/invalid-credential': 'The email address or password is incorrect.',
    'auth/invalid-email': 'Enter a valid email address.',
    'auth/cancelled-popup-request': 'Another Google sign-in attempt replaced this one. Please try again.',
    'auth/internal-error': 'Google sign-in could not start in this browser. Please try again.',
    'auth/network-request-failed': 'Google sign-in could not reach Firebase. Check your connection and try again.',
    'auth/operation-not-allowed': 'Google sign-in is not enabled for this Firebase project.',
    'auth/operation-not-supported-in-this-environment': 'This browser cannot open the Google sign-in flow.',
    'auth/popup-blocked': 'The browser blocked the Google sign-in window. Allow pop-ups and try again.',
    'auth/popup-closed-by-user': 'Google sign-in was cancelled.',
    'auth/too-many-requests': 'Too many attempts. Wait a while before trying again.',
    'auth/unauthorized-domain': 'This site is not authorized for Google sign-in.',
    'auth/user-disabled': 'This account is disabled. Contact an administrator.',
    'auth/web-storage-unsupported': 'This browser blocks the storage required for sign-in.',
    'auth/weak-password': 'Use a password with at least six characters.',
    'auth/expired-action-code': 'This email link has expired. Request a new one.',
    'auth/invalid-action-code': 'This email link is invalid or has already been used.',
  };
  const fallback = 'Authentication could not be completed. Please try again.';
  if (messages[error?.code]) return messages[error.code];
  return import.meta.env.DEV && error?.code ? `${fallback} (${error.code})` : fallback;
}

async function selectPersistence(rememberMe) {
  const auth = requireFirebaseAuth();
  await setPersistence(auth, rememberMe ? browserLocalPersistence : browserSessionPersistence);
  return auth;
}

export async function login(email, password, rememberMe = false) {
  const auth = await selectPersistence(rememberMe);
  return signInWithEmailAndPassword(auth, email.trim(), password);
}

export async function register({ displayName, email, password, passwordConfirmation }) {
  if (password !== passwordConfirmation) {
    const error = new Error('Passwords do not match.');
    error.code = 'password_mismatch';
    throw error;
  }

  const auth = await selectPersistence(false);
  const credential = await createUserWithEmailAndPassword(auth, email.trim(), password);
  const normalizedName = displayName.trim();
  if (normalizedName) await updateProfile(credential.user, { displayName: normalizedName });
  await sendEmailVerification(credential.user, hostedActionSettings());
  return credential;
}

export async function loginWithGoogle(rememberMe = false) {
  const auth = await selectPersistence(rememberMe);
  return signInWithPopup(auth, googleAuthProvider);
}

export async function resendVerificationEmail() {
  const user = requireFirebaseAuth().currentUser;
  if (!user) throw new Error('Sign in before requesting another verification email.');
  await sendEmailVerification(user, hostedActionSettings());
}

export async function requestPasswordReset(email) {
  await sendPasswordResetEmail(requireFirebaseAuth(), email.trim(), hostedActionSettings());
}

export const inspectPasswordResetCode = (code) =>
  verifyPasswordResetCode(requireFirebaseAuth(), code);

export const completePasswordReset = (code, password) =>
  confirmPasswordReset(requireFirebaseAuth(), code, password);

export async function completeEmailVerification(code) {
  const auth = requireFirebaseAuth();
  await applyActionCode(auth, code);
  if (auth.currentUser) {
    await reload(auth.currentUser);
    await getIdToken(auth.currentUser, true);
  }
}

export async function logout() {
  clearUserSpecificState();
  await signOut(requireFirebaseAuth());
}
