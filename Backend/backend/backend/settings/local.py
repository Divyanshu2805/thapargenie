"""Local developer settings. Never use this profile for a public service."""

import os
import secrets

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SPECTACULAR_SETTINGS, database_config, env_bool, env_int, env_list

DEBUG = env_bool('DJANGO_DEBUG', True)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or secrets.token_urlsafe(64)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:5173')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173')

if not os.getenv('DATABASE_URL'):
    raise ImproperlyConfigured(
        'DATABASE_URL is required. Start the local database with `docker compose up -d db` '
        'or point it at the Supabase dev project.'
    )
DATABASES = {
    'default': database_config(
        os.environ['DATABASE_URL'],
        ssl_require=env_bool('DATABASE_SSL_REQUIRE', False),
        conn_max_age=env_int('DATABASE_CONN_MAX_AGE', 0),
    ),
}

if DEBUG:
    SPECTACULAR_SETTINGS = {
        **SPECTACULAR_SETTINGS,
        'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    }

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
