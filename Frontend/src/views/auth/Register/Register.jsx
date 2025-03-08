import { useState } from 'react';
import { Link } from 'react-router-dom';

import { holdAuthRedirect, useSlideNavigate } from '../../../lib/page-slide';
import { authErrorMessage, loginWithGoogle, register } from '../../../utils/auth';
import AuthArrow from '../AuthArrow';
import AuthField from '../AuthField';
import AuthShell from '../AuthShell';
import GoogleIcon from '../GoogleIcon';

export default function Register() {
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirmation, setPasswordConfirmation] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const navigate = useSlideNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!displayName.trim() || !email.trim()) {
      setError('Enter your name and a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Use a password with at least six characters.');
      return;
    }
    if (password !== passwordConfirmation) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    const release = holdAuthRedirect();
    try {
      await register({ displayName, email, password, passwordConfirmation });
      navigate('/chat/', { replace: true, state: { verificationSent: true } });
    } catch (caughtError) {
      setError(authErrorMessage(caughtError));
    } finally {
      release();
      setSubmitting(false);
    }
  };

  // Google accounts arrive already verified, so they go straight to the app.
  const handleGoogleSignUp = async () => {
    setError('');
    setGoogleBusy(true);
    const release = holdAuthRedirect();
    try {
      await loginWithGoogle(false);
      navigate('/chat/', { replace: true });
    } catch (caughtError) {
      setError(authErrorMessage(caughtError));
    } finally {
      release();
      setGoogleBusy(false);
    }
  };

  const busy = submitting || googleBusy;

  return (
    <AuthShell title="Create your account" description="Join ThaparGenie with your Google account or email.">
      <button className="auth-button auth-button--google" disabled={busy} onClick={handleGoogleSignUp} type="button">
        <GoogleIcon />
        {googleBusy ? 'Opening Google…' : 'Sign up with Google'}
      </button>
      <div className="auth-divider" role="separator">
        <span>or sign up with email</span>
      </div>
      <form className="auth-form auth-form--after-divider" onSubmit={handleSubmit} noValidate>
        <AuthField
          autoComplete="name"
          aria-describedby={error ? 'register-error' : undefined}
          aria-invalid={Boolean(error)}
          icon="name"
          id="register-name"
          label="Full name"
          maxLength={150}
          onChange={(event) => setDisplayName(event.target.value)}
          required
          value={displayName}
        />
        <AuthField
          autoComplete="email"
          aria-describedby={error ? 'register-error' : undefined}
          aria-invalid={Boolean(error)}
          icon="email"
          id="register-email"
          label="Email address"
          onChange={(event) => setEmail(event.target.value)}
          required
          type="email"
          value={email}
        />
        <AuthField
          aria-describedby={error ? 'password-help register-error' : 'password-help'}
          aria-invalid={Boolean(error)}
          autoComplete="new-password"
          hint="Use at least six characters."
          hintId="password-help"
          icon="password"
          id="register-password"
          label="Password"
          minLength={6}
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
        <AuthField
          autoComplete="new-password"
          icon="key"
          id="register-password-confirmation"
          label="Confirm password"
          minLength={6}
          onChange={(event) => setPasswordConfirmation(event.target.value)}
          required
          type="password"
          value={passwordConfirmation}
        />
        {error ? <p className="auth-error" id="register-error" role="alert">{error}</p> : null}
        <button className="auth-button" disabled={busy} type="submit">
          {submitting ? 'Creating account…' : 'Create account'}
          <AuthArrow busy={Boolean(submitting)} />
        </button>
      </form>
      <p className="auth-card__footer">
        Already registered? <Link className="auth-link" to="/login/">Sign in</Link>
      </p>
    </AuthShell>
  );
}
