import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import {
  authErrorMessage,
  completeEmailVerification,
  completePasswordReset,
  inspectPasswordResetCode,
} from '../../utils/auth';
import AuthField from './AuthField';
import AuthShell from './AuthShell';

const supportedModes = new Set(['resetPassword', 'verifyEmail', 'recoverEmail']);

export default function AuthAction() {
  const [searchParams] = useSearchParams();
  const mode = searchParams.get('mode');
  const code = searchParams.get('oobCode');
  const [state, setState] = useState({ status: 'loading', email: '', error: '' });
  const [password, setPassword] = useState('');
  const [passwordConfirmation, setPasswordConfirmation] = useState('');

  useEffect(() => {
    let active = true;

    async function inspectAction() {
      if (!code || !supportedModes.has(mode)) {
        setState({ status: 'error', email: '', error: 'This email action link is incomplete or unsupported.' });
        return;
      }

      try {
        if (mode === 'resetPassword') {
          const email = await inspectPasswordResetCode(code);
          if (active) setState({ status: 'reset-ready', email, error: '' });
          return;
        }

        await completeEmailVerification(code);
        if (active) {
          setState({
            status: 'complete',
            email: '',
            error: '',
          });
        }
      } catch (error) {
        if (active) setState({ status: 'error', email: '', error: authErrorMessage(error) });
      }
    }

    inspectAction();
    return () => {
      active = false;
    };
  }, [code, mode]);

  const handlePasswordReset = async (event) => {
    event.preventDefault();
    if (password.length < 6) {
      setState((current) => ({ ...current, error: 'Use a password with at least six characters.' }));
      return;
    }
    if (password !== passwordConfirmation) {
      setState((current) => ({ ...current, error: 'Passwords do not match.' }));
      return;
    }
    setState((current) => ({ ...current, status: 'submitting', error: '' }));
    try {
      await completePasswordReset(code, password);
      setState({ status: 'reset-complete', email: '', error: '' });
    } catch (error) {
      setState((current) => ({ ...current, status: 'reset-ready', error: authErrorMessage(error) }));
    }
  };

  const title = mode === 'resetPassword' ? 'Choose a new password' : 'Confirm your email';

  return (
    <AuthShell title={title}>
      {state.status === 'loading' ? <p className="auth-card__status" role="status">Checking your link…</p> : null}
      {state.status === 'error' ? <p className="auth-error" role="alert">{state.error}</p> : null}
      {state.status === 'complete' ? (
        <p className="auth-success" role="status">
          Your email action is complete. Sign in again if your account status does not update automatically.
        </p>
      ) : null}
      {state.status === 'reset-complete' ? (
        <p className="auth-success" role="status">Your password has been changed. You can now sign in.</p>
      ) : null}
      {['reset-ready', 'submitting'].includes(state.status) ? (
        <form className="auth-form" onSubmit={handlePasswordReset} noValidate>
          <p className="auth-card__description">Resetting the password for {state.email}.</p>
          <AuthField
            autoComplete="new-password"
            aria-describedby={state.error ? 'action-error' : undefined}
            aria-invalid={Boolean(state.error)}
            icon="password"
            id="new-password"
            label="New password"
            minLength={6}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          <AuthField
            autoComplete="new-password"
            aria-describedby={state.error ? 'action-error' : undefined}
            aria-invalid={Boolean(state.error)}
            icon="key"
            id="confirm-new-password"
            label="Confirm new password"
            minLength={6}
            onChange={(event) => setPasswordConfirmation(event.target.value)}
            required
            type="password"
            value={passwordConfirmation}
          />
          {state.error ? <p className="auth-error" id="action-error" role="alert">{state.error}</p> : null}
          <button className="auth-button" disabled={state.status === 'submitting'} type="submit">
            {state.status === 'submitting' ? 'Saving…' : 'Save new password'}
          </button>
        </form>
      ) : null}
      {state.status !== 'loading' ? (
        <p className="auth-card__footer"><Link className="auth-link" to="/login/">Go to sign in</Link></p>
      ) : null}
    </AuthShell>
  );
}
