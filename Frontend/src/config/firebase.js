import { getApp, getApps, initializeApp } from 'firebase/app';
import { connectAuthEmulator, getAuth, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const requiredConfiguration = {
  VITE_FIREBASE_API_KEY: firebaseConfig.apiKey,
  VITE_FIREBASE_AUTH_DOMAIN: firebaseConfig.authDomain,
  VITE_FIREBASE_PROJECT_ID: firebaseConfig.projectId,
  VITE_FIREBASE_APP_ID: firebaseConfig.appId,
};

const missingConfiguration = Object.entries(requiredConfiguration)
  .filter(([, value]) => !value)
  .map(([name]) => name);

export const firebaseConfigurationError = missingConfiguration.length
  ? `Firebase authentication is not configured. Missing: ${missingConfiguration.join(', ')}.`
  : null;

export const firebaseApp = firebaseConfigurationError
  ? null
  : getApps().length > 0
    ? getApp()
    : initializeApp(firebaseConfig);

export const firebaseAuth = firebaseApp ? getAuth(firebaseApp) : null;

if (firebaseAuth && import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL) {
  connectAuthEmulator(firebaseAuth, import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL, {
    disableWarnings: true,
  });
}

export const googleAuthProvider = new GoogleAuthProvider();
googleAuthProvider.setCustomParameters({ prompt: 'select_account' });

export function requireFirebaseAuth() {
  if (!firebaseAuth) {
    throw new Error(firebaseConfigurationError || 'Firebase authentication is unavailable.');
  }
  return firebaseAuth;
}
