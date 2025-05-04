import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import PrivateRoute from './PrivateRoute';

// Staff-only area. The API enforces this too; the route only keeps students out of UI they can't use.
export default function AdminRoute({ children }) {
  return (
    <PrivateRoute>
      <StaffOnly>{children}</StaffOnly>
    </PrivateRoute>
  );
}

function StaffOnly({ children }) {
  const { profile } = useAuth();
  if (!profile?.is_staff) return <Navigate replace to="/chat/" />;
  return children;
}
