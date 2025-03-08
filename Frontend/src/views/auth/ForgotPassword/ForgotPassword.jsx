import { useState } from 'react';
import { Link } from 'react-router-dom';

import { authErrorMessage, requestPasswordReset } from '../../../utils/auth';
import AuthField from '../AuthField';
import AuthShell from '../AuthShell';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!email.trim()) {
      setError('Enter your email address.');
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (caughtError) {
      if (caughtError?.code === 'auth/user-not-found') {
        setSent(true);
      } else {
        setError(authErrorMessage(caughtError));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Reset your password"
      description="Enter your email and we’ll send you a reset link."
    >
      {sent ? (
        <p className="auth-success" role="status">
          Check your inbox for the password-reset link. You can close this page safely.
        </p>
      ) : (
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <AuthField
            autoComplete="email"
            aria-describedby={error ? 'reset-email-error' : undefined}
            aria-invalid={Boolean(error)}
            icon="email"
            id="reset-email"
            label="Email address"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
          {error ? <p className="auth-error" id="reset-email-error" role="alert">{error}</p> : null}
          <button className="auth-button" disabled={submitting} type="submit">
            {submitting ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
      )}
      <p className="auth-card__footer">
        <Link className="auth-link" to="/login/">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
