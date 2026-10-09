"""Deterministic settings for automated tests (always PostgreSQL + pgvector)."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import CACHES, REST_FRAMEWORK, database_config

DEBUG = False
SECRET_KEY = 'test-only-not-a-secret-' + ('x' * 64)
ALLOWED_HOSTS = ['testserver', 'localhost']
CORS_ALLOWED_ORIGINS = ['http://localhost:5173']
CSRF_TRUSTED_ORIGINS = ['http://localhost:5173']

TEST_DATABASE_URL = os.getenv('TEST_DATABASE_URL') or os.getenv('DATABASE_URL')
if not TEST_DATABASE_URL:
    raise ImproperlyConfigured(
        'Tests need PostgreSQL: set TEST_DATABASE_URL (or DATABASE_URL). '
        'Locally: `docker compose up -d db`.'
    )
DATABASES = {'default': database_config(TEST_DATABASE_URL, ssl_require=False, conn_max_age=0)}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
# Tests clear the database cache between cases; keep throttle counters there too so a
# test's requests cannot count against the next one. (The memory cache is tested directly.)
CACHES = {**CACHES, 'throttle': CACHES['default']}
# Throttle behaviour is tested explicitly; keep it out of every other test.
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_CLASSES': ()}
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID') or 'demo-thapargenie'
SSE_INLINE = True
# Tests sign in with made-up addresses; the domain rule has its own tests.
OPEN_ACCESS_EMAIL_DOMAINS = ()
# Admin tests sign in without the second step; two-factor has its own tests.
STAFF_TWO_FACTOR_REQUIRED = False
# Pool threads cannot see a test's transaction; the parallel path has its own test.
RETRIEVE_PARALLEL = False
