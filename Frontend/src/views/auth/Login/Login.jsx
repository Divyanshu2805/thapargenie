import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { holdAuthRedirect, useSlideNavigate } from '../../../lib/page-slide';
import { authErrorMessage, login, loginWithGoogle } from '../../../utils/auth';
import AuthArrow from '../AuthArrow';
import AuthField from '../AuthField';
import AuthShell from '../AuthShell';
import GoogleIcon from '../GoogleIcon';

function safeReturnPath(candidate) {
  return typeof candidate === 'string' && candidate.startsWith('/') && !candidate.startsWith('//')
    ? candidate
    : '/chat/';
}

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(null);
  const location = useLocation();
  const navigate = useSlideNavigate();

  const finishSignIn = () => {
    // A question typed on the landing page goes along, and waits in the chat box.
    const draft = typeof location.state?.draft === 'string' ? location.state.draft : '';
    navigate(safeReturnPath(location.state?.from), { replace: true, state: draft ? { draft } : undefined });
  };

  const handlePasswordLogin = async (event) => {
    event.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError('Enter both your email address and password.');
      return;
    }
    setSubmitting('password');
    const release = holdAuthRedirect();
    try {
      await login(email, password, rememberMe);
      finishSignIn();
    } catch (caughtError) {
      setError(authErrorMessage(caughtError));
    } finally {
      release();
      setSubmitting(null);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
    setSubmitting('google');
    const release = holdAuthRedirect();
    try {
      await loginWithGoogle(rememberMe);
      finishSignIn();
    } catch (caughtError) {
      setError(authErrorMessage(caughtError));
    } finally {
      release();
      setSubmitting(null);
    }
  };

  return (
    <AuthShell title="Welcome back" description="Sign in to continue to ThaparGenie.">
      <button
        className="auth-button auth-button--google"
        disabled={submitting !== null}
        onClick={handleGoogleLogin}
        type="button"
      >
        <GoogleIcon />
        {submitting === 'google' ? 'Opening Google…' : 'Continue with Google'}
      </button>
      <div className="auth-divider" role="separator">
        <span>or sign in with email</span>
      </div>
      <form className="auth-form auth-form--after-divider" onSubmit={handlePasswordLogin} noValidate>
        <AuthField
          autoComplete="email"
          aria-describedby={error ? 'login-error' : undefined}
          aria-invalid={Boolean(error)}
          icon="email"
          id="login-email"
          label="Email address"
          onChange={(event) => setEmail(event.target.value)}
          required
          type="email"
          value={email}
        />
        <AuthField
          autoComplete="current-password"
          aria-describedby={error ? 'login-error' : undefined}
          aria-invalid={Boolean(error)}
          icon="password"
          id="login-password"
          label="Password"
          minLength={6}
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
        />
        <div className="auth-options">
          <label className="auth-check" htmlFor="remember-me">
            <input
              checked={rememberMe}
              id="remember-me"
              onChange={(event) => setRememberMe(event.target.checked)}
              type="checkbox"
            />
            Remember me
          </label>
          <Link className="auth-link" to="/forgot-password/">Forgot password?</Link>
        </div>
        {error ? <p className="auth-error" id="login-error" role="alert">{error}</p> : null}
        <button className="auth-button" disabled={submitting !== null} type="submit">
          {submitting === 'password' ? 'Signing in…' : 'Sign in'}
          <AuthArrow busy={submitting === 'password'} />
        </button>
      </form>
      <p className="auth-card__footer">
        Need an account? <Link className="auth-link" to="/register/">Create one</Link>
      </p>
    </AuthShell>
  );
}
