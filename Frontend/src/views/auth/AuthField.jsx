import { Eye, EyeOff, KeyRound, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { useState } from 'react';

const ICONS = { email: Mail, password: LockKeyhole, name: UserRound, key: KeyRound };

/**
 * A sign-in form field with a leading icon and a floating label.
 * Presentation only: value, validation and submit stay in the owning form.
 */
export default function AuthField({ id, label, icon = 'email', type = 'text', hint, hintId, ...inputProps }) {
  const [revealed, setRevealed] = useState(false);
  const Icon = ICONS[icon] || Mail;
  const isPassword = type === 'password';
  return (
    <div className="auth-field auth-field--float">
      <div className="auth-field__control icon-nudge">
        <Icon className="auth-field__icon" aria-hidden="true" />
        <input id={id} type={isPassword && revealed ? 'text' : type} placeholder=" " {...inputProps} />
        <label htmlFor={id}>{label}</label>
        {isPassword ? (
          <button
            type="button"
            className="auth-field__reveal"
            onClick={() => setRevealed((value) => !value)}
            aria-pressed={revealed}
          >
            {/* Named by its text, not aria-label, so "Password" label lookups find only the field. */}
            <span className="sr-only">{revealed ? 'Hide password' : 'Show password'}</span>
            {revealed ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
          </button>
        ) : null}
      </div>
      {hint ? <small id={hintId}>{hint}</small> : null}
    </div>
  );
}
