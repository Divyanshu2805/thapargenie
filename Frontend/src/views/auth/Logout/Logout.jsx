import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { authErrorMessage, logout } from '../../../utils/auth';
import AuthShell from '../AuthShell';

export default function Logout() {
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    logout()
      .then(() => {
        if (active) navigate('/login/', { replace: true });
      })
      .catch((caughtError) => {
        if (active) setError(authErrorMessage(caughtError));
      });
    return () => {
      active = false;
    };
  }, [navigate]);

  return (
    <AuthShell title="Signing out">
      {error ? <p className="auth-error" role="alert">{error}</p> : <p role="status">Clearing your session…</p>}
    </AuthShell>
  );
}
