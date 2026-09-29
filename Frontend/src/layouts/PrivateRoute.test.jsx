import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  authState: {},
  reloadProfile: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({ useAuth: () => mocks.authState }));

import PrivateRoute from './PrivateRoute';

function LoginDestination() {
  const location = useLocation();
  return <p>Login return: {location.state?.from}</p>;
}

function renderRoute(initialEntry = '/chat/course?year=2026') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/chat/*" element={<PrivateRoute><h1>Protected chat</h1></PrivateRoute>} />
        <Route path="/login/" element={<LoginDestination />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('protected routing', () => {
  beforeEach(() => {
    mocks.authState = {
      initialized: true,
      profile: null,
      profileError: null,
      profileLoading: false,
      reloadProfile: mocks.reloadProfile,
      user: null,
    };
  });

  it('waits for Firebase initialization before redirecting', () => {
    mocks.authState.initialized = false;
    renderRoute();

    expect(screen.getByRole('status')).toHaveTextContent('Checking your session');
    expect(screen.queryByText(/login return/i)).not.toBeInTheDocument();
  });

  it('tells the user the server is waking up while the profile load is retried', () => {
    mocks.authState.initialized = false;
    mocks.authState.profileWaking = true;
    renderRoute();

    expect(screen.getByRole('status')).toHaveTextContent('Waking up the server');
  });

  it('preserves a protected deep link when redirecting a signed-out user', () => {
    renderRoute();

    expect(screen.getByText('Login return: /chat/course?year=2026')).toBeInTheDocument();
  });

  it('shows pending eligibility without rendering protected chat', () => {
    mocks.authState.user = { uid: 'uid-a' };
    mocks.authState.profile = {
      email: 'student@example.edu',
      onboarding_status: 'approval_pending',
    };
    renderRoute();

    expect(screen.getByRole('heading', { name: 'Approval pending' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Protected chat' })).not.toBeInTheDocument();
  });

  it('renders protected content only for a ready account', () => {
    mocks.authState.user = { uid: 'uid-a' };
    mocks.authState.profile = { onboarding_status: 'ready' };
    renderRoute();

    expect(screen.getByRole('heading', { name: 'Protected chat' })).toBeInTheDocument();
  });
});
