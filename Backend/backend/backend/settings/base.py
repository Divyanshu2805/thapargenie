"""Settings shared by every environment."""

import os
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int(name, default):
    return int(os.getenv(name, str(default)))


DATABASE_STATEMENT_TIMEOUT_MS = env_int("DATABASE_STATEMENT_TIMEOUT_MS", 30000)
DATABASE_LOCK_TIMEOUT_MS = env_int("DATABASE_LOCK_TIMEOUT_MS", 5000)
# Supabase transaction pooler (:6543): no server-side cursors, no session settings.
DATABASE_TRANSACTION_POOLING = env_bool("DATABASE_TRANSACTION_POOLING", False)


def database_config(url, *, ssl_require, conn_max_age):
    """Postgres connection settings shared by every profile."""
    if not url.startswith(("postgres://", "postgresql://")):
        raise ImproperlyConfigured("DATABASE_URL must point at PostgreSQL (pgvector is required).")
    config = dj_database_url.parse(
        url,
        conn_max_age=conn_max_age,
        conn_health_checks=True,
        ssl_require=ssl_require,
    )
    config.setdefault("OPTIONS", {}).update(
        {
            "connect_timeout": env_int("DATABASE_CONNECT_TIMEOUT_SECONDS", 5),
            # Honoured on direct connections; poolers drop it, so common/db.py also
            # sets these (and the vector search settings) on every new connection.
            "options": (
                f"-c statement_timeout={DATABASE_STATEMENT_TIMEOUT_MS} "
                f"-c lock_timeout={DATABASE_LOCK_TIMEOUT_MS}"
            ),
        }
    )
    # Transaction-mode poolers (Supabase :6543) cannot keep server-side cursors.
    config["DISABLE_SERVER_SIDE_CURSORS"] = DATABASE_TRANSACTION_POOLING
    return config


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "userauths",
    "api",
    "common",
    "knowledge",
    "rag",
    "chat",
    "access",
    "notices",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "api.middleware.RequestIDMiddleware",
    "common.observability.RequestContextMiddleware",
    "common.headers.SecurityHeadersMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"
AUTH_USER_MODEL = "userauths.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# Quotas, "today" in stats and retention dates follow Indian time; the database stores UTC.
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@localhost")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("api.authentication.FirebaseAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "api.permissions.HasVerifiedEligibleIdentity",
    ),
    "EXCEPTION_HANDLER": "common.errors.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.UserRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("THROTTLE_USER", "120/min"),
        "ask": os.getenv("THROTTLE_ASK", "6/min"),
        "suggest": os.getenv("THROTTLE_SUGGEST", "10/min"),
        "admin_write": os.getenv("THROTTLE_ADMIN_WRITE", "30/min"),
        "export": os.getenv("THROTTLE_EXPORT", "5/hour"),
        "client_error": os.getenv("THROTTLE_CLIENT_ERROR", "20/min"),
        "site_feedback": os.getenv("THROTTLE_SITE_FEEDBACK", "5/hour"),
        "admin_export": os.getenv("THROTTLE_ADMIN_EXPORT", "30/hour"),
        "shared_view": os.getenv("THROTTLE_SHARED_VIEW", "60/min"),
    },
    # How many proxies sit in front of the app and append X-Forwarded-For. 0 (local)
    # ignores the header; Render needs 1. Without it, anonymous clients could forge
    # their address and dodge the per-address rate limit.
    "NUM_PROXIES": env_int("TRUSTED_PROXY_COUNT", 0),
}

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
CORS_ALLOW_HEADERS = (*default_headers, "x-request-id")
FIREBASE_AUTH_EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
FIREBASE_ALLOWED_SIGN_IN_PROVIDERS = tuple(
    env_list("FIREBASE_ALLOWED_SIGN_IN_PROVIDERS", "password,google.com")
)
FIREBASE_RECENT_AUTH_SECONDS = int(os.getenv("FIREBASE_RECENT_AUTH_SECONDS", "300"))
# A freshly issued token is "used too early" if this server's clock trails Google's by even
# a second, so the first request after signing in would fail. Allow a little drift.
FIREBASE_CLOCK_SKEW_SECONDS = int(os.getenv("FIREBASE_CLOCK_SKEW_SECONDS", "10"))
# Returns True when new verified users are approved without an admin.
IDENTITY_OPEN_ACCESS = "access.policy.open_access_enabled"
if FIREBASE_RECENT_AUTH_SECONDS < 0:
    raise ValueError("FIREBASE_RECENT_AUTH_SECONDS cannot be negative.")
if not 0 <= FIREBASE_CLOCK_SKEW_SECONDS <= 60:
    raise ValueError("FIREBASE_CLOCK_SKEW_SECONDS must be between 0 and 60.")
if FIREBASE_AUTH_EMULATOR_HOST and "://" in FIREBASE_AUTH_EMULATOR_HOST:
    raise ValueError("FIREBASE_AUTH_EMULATOR_HOST must omit the URL scheme.")

EXTERNAL_HTTP_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_HTTP_TIMEOUT_SECONDS", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(2 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(2 * 1024 * 1024)))

# Shared across gunicorn workers so throttles count per user, not per process.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    },
}

DJANGO_ADMIN_ENABLED = env_bool("DJANGO_ADMIN_ENABLED", True)
SSE_INLINE = False

SPECTACULAR_SETTINGS = {
    "TITLE": "ThaparGenie API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    # Several components have a "role" field; name the chat message one explicitly.
    "ENUM_NAME_OVERRIDES": {
        "MessageRoleEnum": "chat.models.Role",
        "SiteFeedbackKindEnum": "chat.models.SiteFeedbackKind",
    },
}

# LLM providers. Model names come from env so they can change without a deploy.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "gemini").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
CHAT_MODEL = os.getenv("CHAT_MODEL", "").strip()
FAST_MODEL = os.getenv("FAST_MODEL", "").strip()
EMBED_MODEL = os.getenv("EMBED_MODEL", "").strip()
EMBED_DIMENSIONS = env_int("EMBED_DIMENSIONS", 768)
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_ATTEMPTS = env_int("LLM_MAX_ATTEMPTS", 3)
# Reasoning level for the quick structured calls (analysis, rerank). "" = model default.
FAST_THINKING = os.getenv("FAST_THINKING", "minimal").strip()
# Reasoning level for the streamed answer. "low" cuts time-to-first-token from ~14 s to
# ~8 s with no measured loss on the eval set; "" restores the model default.
ANSWER_THINKING = os.getenv("ANSWER_THINKING", "low").strip()
# Run the keyword search on its own connection while the queries are embedded.
RETRIEVE_PARALLEL = env_bool("RETRIEVE_PARALLEL", True)
# Texts per embedding request; lower it if the free tier returns 429s.
EMBED_BATCH_SIZE = env_int("EMBED_BATCH_SIZE", 50)

# Supabase Storage (private bucket for uploaded originals).
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "documents").strip()

# Ingestion limits.
INGEST_URL_ALLOWLIST = tuple(
    env_list("INGEST_URL_ALLOWLIST", "thapar.edu,*.thapar.edu,static.npfs.co")
)
INGEST_MAX_FILE_MB = env_int("INGEST_MAX_FILE_MB", 25)
INGEST_MAX_PAGES = env_int("INGEST_MAX_PAGES", 300)

# Retention, applied daily by `manage.py purge_data`.
RETENTION_CONVERSATION_DAYS = env_int("RETENTION_CONVERSATION_DAYS", 180)
RETENTION_TRACE_DAYS = env_int("RETENTION_TRACE_DAYS", 30)
RETENTION_USAGE_DAYS = env_int("RETENTION_USAGE_DAYS", 400)  # 13 months, rounded up
RETENTION_AUDIT_DAYS = env_int("RETENTION_AUDIT_DAYS", 365)
RETENTION_FAILED_DOCUMENT_DAYS = env_int("RETENTION_FAILED_DOCUMENT_DAYS", 30)
RETENTION_SITE_FEEDBACK_DAYS = env_int("RETENTION_SITE_FEEDBACK_DAYS", 365)
RETENTION_NOTICE_DAYS = env_int("RETENTION_NOTICE_DAYS", 365)  # after expiry

PROVIDERS = {"gemini", "openai"}
if LLM_PROVIDER not in PROVIDERS or EMBED_PROVIDER not in PROVIDERS:
    raise ImproperlyConfigured("LLM_PROVIDER and EMBED_PROVIDER must be gemini or openai.")
if EMBED_DIMENSIONS != 768:
    raise ImproperlyConfigured("EMBED_DIMENSIONS must be 768 to match the vector columns.")
if SUPABASE_URL and not SUPABASE_URL.startswith("https://"):
    raise ImproperlyConfigured("SUPABASE_URL must use https.")
if not 1 <= INGEST_MAX_FILE_MB <= 50:
    raise ImproperlyConfigured("INGEST_MAX_FILE_MB must be between 1 and 50.")
if not 1 <= INGEST_MAX_PAGES <= 2000:
    raise ImproperlyConfigured("INGEST_MAX_PAGES must be between 1 and 2000.")
for _name in ("RETENTION_CONVERSATION_DAYS", "RETENTION_TRACE_DAYS", "RETENTION_USAGE_DAYS",
              "RETENTION_AUDIT_DAYS", "RETENTION_FAILED_DOCUMENT_DAYS",
              "RETENTION_SITE_FEEDBACK_DAYS", "RETENTION_NOTICE_DAYS"):
    if not 1 <= globals()[_name] <= 3650:
        raise ImproperlyConfigured(f"{_name} must be between 1 and 3650 days.")

# Observability. LOG_FORMAT=json for log search tools.
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # Order matters: the context filter fills request_id before redaction runs.
        "request_context": {"()": "common.observability.RequestContextFilter"},
        "redact_secrets": {"()": "backend.logging.RedactSecretsFilter"},
    },
    "formatters": {
        "text": {
            "format": "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s "
                      "user=%(user_id)s %(message)s",
        },
        "json": {"()": "common.observability.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context", "redact_secrets"],
            "formatter": "json" if LOG_FORMAT == "json" else "text",
        },
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        # Third-party HTTP clients log every request at INFO; keep only problems.
        **{name: {"level": "WARNING"} for name in ("httpx", "httpcore", "google_genai", "openai")},
        # One line per API request; set LOG_ACCESS=false to silence.
        "thapargpt.access": {"level": "INFO" if env_bool("LOG_ACCESS", True) else "WARNING"},
        # Django's own request logger repeats every 4xx/5xx the handler above already logs.
        "django.request": {"level": "ERROR"},
    },
}
