import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { onIdTokenChanged } from 'firebase/auth';

import { firebaseAuth, firebaseConfigurationError } from '../config/firebase';
import { getCurrentUserProfile } from '../utils/apiClient';
import { clearUserSpecificState } from '../utils/session';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(() =>
    firebaseAuth ? null : new Error(firebaseConfigurationError),
  );
  const [initialized, setInitialized] = useState(() => !firebaseAuth);
  const [profileLoading, setProfileLoading] = useState(false);
  const requestGeneration = useRef(0);
  const previousUid = useRef(undefined);

  const loadProfile = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setProfileLoading(true);
    setProfileError(null);
    try {
      const nextProfile = await getCurrentUserProfile();
      if (generation === requestGeneration.current) setProfile(nextProfile);
      return nextProfile;
    } catch (error) {
      if (generation === requestGeneration.current) {
        setProfile(null);
        setProfileError(error);
      }
      throw error;
    } finally {
      if (generation === requestGeneration.current) setProfileLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!firebaseAuth) return undefined;

    return onIdTokenChanged(firebaseAuth, async (nextUser) => {
      const nextUid = nextUser?.uid || null;
      if (previousUid.current !== undefined && previousUid.current !== nextUid) {
        clearUserSpecificState();
      }
      previousUid.current = nextUid;
      setUser(nextUser);
      setProfile(null);
      setProfileError(null);

      if (!nextUser) {
        requestGeneration.current += 1;
        setProfileLoading(false);
        setInitialized(true);
        return;
      }

      try {
        await loadProfile();
      } catch {
        // profileError is rendered by the route boundary.
      } finally {
        setInitialized(true);
      }
    });
  }, [loadProfile]);

  const value = {
    initialized,
    profile,
    profileError,
    profileLoading,
    reloadProfile: loadProfile,
    user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
