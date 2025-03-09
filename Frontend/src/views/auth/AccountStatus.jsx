import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { onSignInPage, slideTo } from '../../lib/page-slide';
import { authErrorMessage, logout, resendVerificationEmail } from '../../utils/auth';
import AuthShell from './AuthShell';

const statusCopy = {
  approval_pending: {
    title: 'Approval pending',
    message: 'Your email is verified. An administrator still needs to approve your account before chat is available.',
  },
  access_denied: {
    title: 'Account not eligible',
    message: 'This account is not eligible for access. Contact an administrator if you think this is a mistake.',
  },
  access_suspended: {
    title: 'Account suspended',
    message: 'Access for this account is suspended. Contact an administrator for help.',
  },
};

export default function AccountStatus({ profile, error, onRetry }) {
  const [feedback, setFeedback] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const onboardingStatus = profile?.onboarding_status;
  const copy = statusCopy[onboardingStatus] || {
    title: error ? 'Unable to check account' : 'Verify your email',
    message: error
      ? error.message
      : 'Open the verification link sent to your inbox, then return here. You may resend the message below.',
  };

  const handleResend = async () => {
    setBusy(true);
    setFeedback('');
    setActionError('');
    try {
      await resendVerificationEmail();
      setFeedback('A new verification email has been sent.');
    } catch (caughtError) {
      setActionError(authErrorMessage(caughtError));
    } finally {
      setBusy(false);
    }
  };

  const handleLogout = () => {
    setBusy(true);
    setActionError('');
    slideTo(
      async () => {
        try {
          await logout();
          navigate('/login/', { replace: true });
        } catch (caughtError) {
          setActionError(authErrorMessage(caughtError));
          setBusy(false);
        }
      },
      { ready: onSignInPage, back: true },
    );
  };

  return (
    <AuthShell title={copy.title} description={copy.message}>
      {profile?.email ? <p className="auth-card__status">Signed in as {profile.email}</p> : null}
      {feedback ? <p className="auth-success" role="status">{feedback}</p> : null}
      {actionError ? <p className="auth-error" role="alert">{actionError}</p> : null}
      <div className="auth-actions">
        {onboardingStatus === 'email_verification_required' ? (
          <button className="auth-button" disabled={busy} onClick={handleResend} type="button">
            {busy ? 'Sending…' : 'Resend verification email'}
          </button>
        ) : null}
        {error ? (
          <button className="auth-button" disabled={busy} onClick={onRetry} type="button">
            Try again
          </button>
        ) : null}
        <button className="auth-button auth-button--secondary" disabled={busy} onClick={handleLogout} type="button">
          Sign out
        </button>
      </div>
    </AuthShell>
  );
}
