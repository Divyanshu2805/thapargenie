import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ auth: null }));

vi.mock('../auth/AuthContext', () => ({ useAuth: () => mocks.auth }));

import AdminRoute from './AdminRoute';

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login/" element={<h1>Login page</h1>} />
        <Route path="/chat/" element={<h1>Chat page</h1>} />
        <Route
          path="/admin/"
          element={
            <AdminRoute>
              <h1>Admin dashboard</h1>
            </AdminRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function signedIn(profile) {
  return {
    initialized: true,
    profile: { onboarding_status: 'ready', ...profile },
    profileError: null,
    profileLoading: false,
    reloadProfile: vi.fn(),
    user: { uid: 'u1' },
  };
}

describe('AdminRoute', () => {
  beforeEach(() => {
    mocks.auth = null;
  });

  it('shows the admin area to staff', () => {
    mocks.auth = signedIn({ is_staff: true });
    renderAt('/admin/');
    expect(screen.getByRole('heading', { name: 'Admin dashboard' })).toBeInTheDocument();
  });

  it('sends approved students back to chat', () => {
    mocks.auth = signedIn({ is_staff: false });
    renderAt('/admin/');
    expect(screen.getByRole('heading', { name: 'Chat page' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Admin dashboard' })).not.toBeInTheDocument();
  });

  it('sends signed-out visitors to login', () => {
    mocks.auth = { ...signedIn({}), user: null, profile: null };
    renderAt('/admin/');
    expect(screen.getByRole('heading', { name: 'Login page' })).toBeInTheDocument();
  });

  it('shows the account status screen to staff who are not approved', () => {
    mocks.auth = signedIn({ is_staff: true, onboarding_status: 'access_suspended' });
    renderAt('/admin/');
    expect(screen.getByRole('heading', { name: 'Account suspended' })).toBeInTheDocument();
  });
});
