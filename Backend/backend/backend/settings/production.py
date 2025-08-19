"""Fail-closed settings for the deployed API."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import (
    EMBED_PROVIDER,
    FIREBASE_ALLOWED_SIGN_IN_PROVIDERS,
    FIREBASE_AUTH_EMULATOR_HOST,
    LLM_PROVIDER,
    SENTRY_DSN,
    SENTRY_TRACES_SAMPLE_RATE,
    STORAGE_BACKEND,
    database_config,
    env_bool,
    env_list,
)
from .base import (
    MIDDLEWARE as BASE_MIDDLEWARE,
)


def required(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} is required in production.')
    return value


DEBUG = False
SECRET_KEY = required('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must contain at least 50 characters.')

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must be an explicit non-empty list.')

CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
if any(not origin.startswith('https://') for origin in CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('Production browser origins must use HTTPS.')

FIREBASE_PROJECT_ID = required('FIREBASE_PROJECT_ID')
if FIREBASE_AUTH_EMULATOR_HOST:
    raise ImproperlyConfigured('FIREBASE_AUTH_EMULATOR_HOST is forbidden outside local/test use.')
if not FIREBASE_ALLOWED_SIGN_IN_PROVIDERS:
    raise ImproperlyConfigured('FIREBASE_ALLOWED_SIGN_IN_PROVIDERS cannot be empty.')

DATABASES = {
    'default': database_config(
        required('DATABASE_URL'),
        ssl_require=True,
        conn_max_age=int(os.getenv('DATABASE_CONN_MAX_AGE', '60')),
    ),
}

if 'offline' in (LLM_PROVIDER, EMBED_PROVIDER):
    raise ImproperlyConfigured('The offline AI provider is for local tests only.')
if STORAGE_BACKEND != 'supabase':
    raise ImproperlyConfigured('STORAGE_BACKEND must be supabase in production.')
if LLM_PROVIDER == 'gemini' or EMBED_PROVIDER == 'gemini':
    required('GEMINI_API_KEY')
if LLM_PROVIDER == 'openai' or EMBED_PROVIDER == 'openai':
    required('OPENAI_API_KEY')
for model_setting in ('CHAT_MODEL', 'FAST_MODEL', 'EMBED_MODEL'):
    required(model_setting)
SUPABASE_URL = required('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = required('SUPABASE_SERVICE_ROLE_KEY')

DJANGO_ADMIN_ENABLED = env_bool('DJANGO_ADMIN_ENABLED', False)

MIDDLEWARE = [*BASE_MIDDLEWARE]
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Error tracking (optional): active only when SENTRY_DSN is set.
from common.observability import init_sentry  # noqa: E402

init_sentry(SENTRY_DSN, environment='production', traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE)
