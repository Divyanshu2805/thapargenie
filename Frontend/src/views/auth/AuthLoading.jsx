import { LogoGlyph } from '@/components/brand/Brand';

import './AuthShell.css';

const WAKING_MESSAGE = 'Waking up the server. The first load after a quiet spell can take up to a minute…';

export default function AuthLoading({ message = 'Checking your session…', waking = false }) {
  return (
    <main className="auth-loading" aria-live="polite">
      <span className="auth-loading__mark" aria-hidden="true">
        <LogoGlyph motion="loop" />
      </span>
      <p className="auth-card__status" role="status">{waking ? WAKING_MESSAGE : message}</p>
    </main>
  );
}
