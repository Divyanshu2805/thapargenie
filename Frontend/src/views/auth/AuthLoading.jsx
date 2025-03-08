import { LogoGlyph } from '@/components/brand/Brand';

import './AuthShell.css';

export default function AuthLoading({ message = 'Checking your session…' }) {
  return (
    <main className="auth-loading" aria-live="polite">
      <span className="auth-loading__mark" aria-hidden="true">
        <LogoGlyph motion="loop" />
      </span>
      <p className="auth-card__status" role="status">{message}</p>
    </main>
  );
}
