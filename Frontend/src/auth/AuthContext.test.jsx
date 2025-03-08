import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: {},
  clearUserSpecificState: vi.fn(),
  getCurrentUserProfile: vi.fn(),
  listener: null,
}));

vi.mock('firebase/auth', () => ({
  onIdTokenChanged: (_auth, listener) => {
    mocks.listener = listener;
    return vi.fn();
  },
}));

vi.mock('../config/firebase', () => ({
  firebaseAuth: mocks.auth,
  firebaseConfigurationError: null,
}));

vi.mock('../utils/apiClient', () => ({
  getCurrentUserProfile: mocks.getCurrentUserProfile,
}));

vi.mock('../utils/session', () => ({
  clearUserSpecificState: mocks.clearUserSpecificState,
}));

import { AuthProvider, useAuth } from './AuthContext';

function Probe() {
  const { initialized, profile, user } = useAuth();
  return <p>{initialized ? `${user?.uid || 'none'}:${profile?.onboarding_status || 'none'}` : 'initializing'}</p>;
}

describe('AuthProvider account changes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getCurrentUserProfile.mockResolvedValue({ onboarding_status: 'ready' });
  });

  it('tracks token changes and clears user-specific state between accounts and on logout', async () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByText('initializing')).toBeInTheDocument();

    await act(async () => mocks.listener({ uid: 'user-a' }));
    expect(screen.getByText('user-a:ready')).toBeInTheDocument();
    expect(mocks.clearUserSpecificState).not.toHaveBeenCalled();

    await act(async () => mocks.listener({ uid: 'user-a' }));
    expect(mocks.clearUserSpecificState).not.toHaveBeenCalled();

    await act(async () => mocks.listener({ uid: 'user-b' }));
    expect(screen.getByText('user-b:ready')).toBeInTheDocument();
    expect(mocks.clearUserSpecificState).toHaveBeenCalledTimes(1);

    await act(async () => mocks.listener(null));
    expect(screen.getByText('none:none')).toBeInTheDocument();
    expect(mocks.clearUserSpecificState).toHaveBeenCalledTimes(2);
  });
});
