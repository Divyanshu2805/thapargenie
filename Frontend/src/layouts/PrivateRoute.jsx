import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import AccountStatus from '../views/auth/AccountStatus';
import AuthLoading from '../views/auth/AuthLoading';

export default function PrivateRoute({ children }) {
  const { initialized, profile, profileError, profileLoading, reloadProfile, user } = useAuth();
  const location = useLocation();

  if (!initialized) return <AuthLoading />;
  if (!user) {
    return (
      <Navigate
        replace
        state={{ from: `${location.pathname}${location.search}` }}
        to="/login/"
      />
    );
  }
  if (profileLoading) return <AuthLoading message="Checking account access…" />;
  if (profileError || profile?.onboarding_status !== 'ready') {
    return <AccountStatus error={profileError} onRetry={reloadProfile} profile={profile} />;
  }

  return children ?? <Outlet />;
}
