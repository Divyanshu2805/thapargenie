// Content-Security-Policy for the built SPA. Injected into
// index.html at build time as a <meta> tag, from the same VITE_* values the app uses,
// so it follows whichever API and Firebase project a build targets. `frame-ancestors`
// cannot be set by <meta>; the hosting config sends it as a header.

function originOf(url) {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

export function buildCsp({ apiBaseUrl, firebaseAuthDomain, authEmulatorUrl }) {
  const api = originOf(apiBaseUrl);
  if (!api) throw new Error('VITE_API_BASE_URL must be an absolute URL to build the CSP.');
  const authHost = firebaseAuthDomain ? `https://${firebaseAuthDomain}` : null;
  // Only end-to-end builds set an emulator URL; a build for a real (https) API never may.
  const emulator = authEmulatorUrl ? originOf(authEmulatorUrl) : null;
  if (authEmulatorUrl && (!emulator || api.startsWith('https://'))) {
    throw new Error('VITE_FIREBASE_AUTH_EMULATOR_URL is for local end-to-end builds only.');
  }

  const directives = {
    'default-src': ["'self'"],
    // Firebase Auth loads gapi from apis.google.com for the Google sign-in popup.
    'script-src': ["'self'", 'https://apis.google.com'],
    // Toasts inject a <style> element at runtime; no user content reaches styles.
    'style-src': ["'self'", "'unsafe-inline'"],
    'font-src': ["'self'"],
    // Google profile photos in the account menu.
    'img-src': ["'self'", 'data:', 'https://lh3.googleusercontent.com'],
    'connect-src': [
      "'self'",
      api,
      'https://identitytoolkit.googleapis.com',
      'https://securetoken.googleapis.com',
      'https://www.googleapis.com',
      'https://apis.google.com',
      emulator,
    ].filter(Boolean),
    // The Firebase Auth helper iframe and the Google account chooser.
    'frame-src': [authHost, 'https://accounts.google.com'].filter(Boolean),
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'worker-src': ["'none'"],
    'manifest-src': ["'self'"],
  };
  if (api.startsWith('https://')) directives['upgrade-insecure-requests'] = [];

  return Object.entries(directives)
    .map(([name, values]) => [name, ...new Set(values)].join(' '))
    .join('; ');
}

/** Origins every page talks to while Firebase Auth starts; connecting early saves a
 * round trip on the first load. */
export function preconnectOrigins(firebaseAuthDomain) {
  return [firebaseAuthDomain ? `https://${firebaseAuthDomain}` : null, 'https://apis.google.com'].filter(Boolean);
}

/** Vite plugin: adds the CSP <meta> to index.html in production builds only (the dev
 * server needs inline scripts and websockets for hot reload). */
export function cspPlugin(env) {
  return {
    name: 'thapargenie-csp',
    apply: 'build',
    transformIndexHtml() {
      const content = buildCsp({
        apiBaseUrl: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1/',
        firebaseAuthDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
        authEmulatorUrl: env.VITE_FIREBASE_AUTH_EMULATOR_URL,
      });
      return [
        { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content }, injectTo: 'head-prepend' },
        ...preconnectOrigins(env.VITE_FIREBASE_AUTH_DOMAIN).map((href) => ({
          tag: 'link',
          attrs: { rel: 'preconnect', href, crossorigin: '' },
          injectTo: 'head',
        })),
      ];
    },
  };
}
