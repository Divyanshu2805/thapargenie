/**
 * The arrow on the Sign in / Create account buttons: a chevron at rest that grows a shaft
 * and glides forward on hover. While the form submits it slips away and a fine spinner
 * takes its place.
 */
export default function AuthArrow({ busy = false }) {
  return (
    <span className={busy ? 'auth-arrow auth-arrow--busy' : 'auth-arrow'} aria-hidden="true">
      <svg className="auth-arrow__svg" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path className="auth-arrow__shaft" d="M0 5h7" />
        <path className="auth-arrow__tip" d="M1 1l4 4-4 4" />
      </svg>
      <span className="auth-arrow__spinner" />
    </span>
  );
}
