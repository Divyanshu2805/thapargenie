// Sends uncaught browser errors to the API (`POST client-errors/`), where they join the
// server logs and Sentry. Reports carry no token, no query string and no user content:
// only the error message, a trimmed stack and the page path.
import { API_BASE_URL } from '../utils/constants';

const MAX_REPORTS_PER_PAGE = 10;
const RELEASE = import.meta.env.VITE_APP_RELEASE || 'dev';
const sent = new Set();
let count = 0;

// Errors that are expected, already shown to the user, or not ours.
const IGNORED = [
  /ResizeObserver loop/i,
  /request was cancelled/i,
  /AbortError/i,
  /Non-Error promise rejection captured/i,
];

export function isChunkLoadError(error) {
  const text = `${error?.name || ''} ${error?.message || error || ''}`;
  return /ChunkLoadError|Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i.test(
    text,
  );
}

export function buildReport(error, kind = 'error') {
  const message = String(error?.message || error || 'Unknown error').slice(0, 500);
  const stack = String(error?.stack || '').slice(0, 4000);
  return { message, stack, kind, path: window.location.pathname.slice(0, 200), release: RELEASE };
}

export function shouldReport(error) {
  if (!error) return false;
  // ApiErrors are handled in the UI and already logged by the server.
  if (error.name === 'ApiError') return false;
  const text = String(error?.message || error);
  if (IGNORED.some((pattern) => pattern.test(text))) return false;
  // Browser extensions inject scripts into every page; their errors are not ours.
  if (/(chrome|moz|safari)-extension:\/\//.test(String(error?.stack || ''))) return false;
  return true;
}

export function reportError(error, kind = 'error') {
  if (!shouldReport(error) || count >= MAX_REPORTS_PER_PAGE) return;
  const report = buildReport(error, kind);
  const key = `${report.kind}:${report.message}`;
  if (sent.has(key)) return;
  sent.add(key);
  count += 1;
  try {
    fetch(new URL('client-errors/', API_BASE_URL), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Reporting must never throw.
  }
}

export function installGlobalErrorHandlers() {
  window.addEventListener('error', (event) => reportError(event.error || event.message, 'error'));
  window.addEventListener('unhandledrejection', (event) => reportError(event.reason, 'rejection'));
  // After a deploy, an open tab may ask for old chunk files that no longer exist.
  // Vite signals it here; reload once to pick up the new build.
  window.addEventListener('vite:preloadError', (event) => {
    event.preventDefault();
    reloadForNewVersion(event.payload);
  });
}

const RELOAD_KEY = 'thapargpt:reloaded-for-version';

/** Reload once per session to fetch the new build; report if that didn't help. */
export function reloadForNewVersion(error) {
  let alreadyReloaded = false;
  try {
    alreadyReloaded = window.sessionStorage.getItem(RELOAD_KEY) === '1';
    window.sessionStorage.setItem(RELOAD_KEY, '1');
  } catch {
    // Storage blocked: fall through and reload anyway.
  }
  if (alreadyReloaded) {
    reportError(error, 'chunk');
    return false;
  }
  window.location.reload();
  return true;
}

export function _resetForTests() {
  sent.clear();
  count = 0;
}
