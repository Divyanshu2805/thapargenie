import { defineConfig } from '@playwright/test';

// End-to-end runs: an API on :8020 with the offline AI provider and
// in-memory storage, and Vite on :5174, both talking to the Firebase Auth emulator
// (started around this run with `firebase emulators:exec`). The ports differ from the
// dev servers (:8010, :5173) so both can run side by side.
const API_PORT = 8020;
const WEB_PORT = 5174;
const EMULATOR = process.env.FIREBASE_AUTH_EMULATOR_HOST || '127.0.0.1:9099';
const PROJECT_ID = 'demo-thapargpt';
const E2E_DATABASE_URL = process.env.E2E_DATABASE_URL || 'postgres://thapargpt:thapargpt@127.0.0.1:54329/thapargpt_e2e';
// Relative to Backend/backend (the API server's working directory).
const PYTHON = process.env.E2E_PYTHON || (process.platform === 'win32' ? '..\\.venv\\Scripts\\python.exe' : 'python');
const WEB_URL = `http://localhost:${WEB_PORT}`;

// Everything the API needs is set here, so nothing is taken from Backend/backend/.env
// (explicit variables win over that file).
const apiEnv = {
  APP_ENV: 'local',
  DJANGO_DEBUG: 'false',
  DJANGO_SECRET_KEY: 'e2e-only-secret-key-not-used-anywhere-else-0123456789abcdef',
  DATABASE_URL: E2E_DATABASE_URL,
  DATABASE_SSL_REQUIRE: 'false',
  CORS_ALLOWED_ORIGINS: WEB_URL,
  CSRF_TRUSTED_ORIGINS: WEB_URL,
  FIREBASE_PROJECT_ID: PROJECT_ID,
  FIREBASE_AUTH_EMULATOR_HOST: EMULATOR,
  GOOGLE_APPLICATION_CREDENTIALS: '',
  LLM_PROVIDER: 'offline',
  EMBED_PROVIDER: 'offline',
  CHAT_MODEL: 'offline-chat',
  FAST_MODEL: 'offline-fast',
  EMBED_MODEL: 'offline-embed',
  STORAGE_BACKEND: 'memory',
  SUPABASE_URL: '',
  SUPABASE_SERVICE_ROLE_KEY: '',
  OFFLINE_LLM_DELAY_MS: '60',
  LOG_ACCESS: 'false',
  PYTHONUNBUFFERED: '1',
};

const manage = (command) => `${PYTHON} manage.py ${command}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  reporter: process.env.CI ? [['line'], ['html', { open: 'never' }]] : 'line',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || WEB_URL,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : [
        {
          command: [
            manage('migrate --no-input'),
            manage('createcachetable'),
            manage('seed_e2e'),
            manage(`runserver 127.0.0.1:${API_PORT} --noreload`),
          ].join(' && '),
          cwd: '../Backend/backend',
          url: `http://127.0.0.1:${API_PORT}/health/ready/`,
          env: apiEnv,
          timeout: 180_000,
          reuseExistingServer: false,
          stdout: 'pipe',
        },
        {
          // A production build (with its CSP), not the dev server: closer to what ships, and
          // React's development double effects would replay one-time email action codes.
          command: `npx vite build --outDir dist-e2e --emptyOutDir && npx vite preview --outDir dist-e2e --port ${WEB_PORT} --strictPort`,
          url: WEB_URL,
          env: {
            VITE_API_BASE_URL: `http://127.0.0.1:${API_PORT}/api/v1/`,
            VITE_FIREBASE_API_KEY: 'demo-api-key',
            VITE_FIREBASE_AUTH_DOMAIN: `${PROJECT_ID}.firebaseapp.com`,
            VITE_FIREBASE_PROJECT_ID: PROJECT_ID,
            VITE_FIREBASE_APP_ID: '1:000000000000:web:e2e',
            VITE_FIREBASE_AUTH_EMULATOR_URL: `http://${EMULATOR}`,
          },
          timeout: 120_000,
          reuseExistingServer: false,
        },
      ],
});
