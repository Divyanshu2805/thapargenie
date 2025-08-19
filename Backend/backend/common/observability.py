"""Request-scoped logging context, access logs, JSON log output and optional Sentry.

Every log line carries the request id: `RequestContextMiddleware` puts it in a context
variable, `RequestContextFilter` copies it onto each record. Work handed to another
thread (the SSE pump) runs in a copy of the context, so it keeps the id too.
"""

import contextvars
import json
import logging
import os
import time

request_id_var = contextvars.ContextVar('request_id', default='-')
user_id_var = contextvars.ContextVar('user_id', default='-')

access_logger = logging.getLogger('thapargpt.access')

# Paths polled by uptime checks and keep-alive pings; logging them only adds noise.
QUIET_PREFIXES = ('/health/',)


class RequestContextMiddleware:
    """Runs after `api.middleware.RequestIDMiddleware` has assigned `request.request_id`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id_var.set(getattr(request, 'request_id', None) or '-')
        user_id_var.set('-')
        started = time.monotonic()
        response = self.get_response(request)
        if not request.path.startswith(QUIET_PREFIXES):
            user = getattr(request, 'user', None)
            signed_in = getattr(user, 'is_authenticated', False)
            user_id = getattr(user, 'pk', None) if signed_in else None
            if user_id is not None:
                user_id_var.set(str(user_id))
            # The path only: query strings can hold search terms. No bodies, ever.
            access_logger.info(
                '%s %s %s %dms', request.method, request.path, response.status_code,
                round((time.monotonic() - started) * 1000),
                extra={'user_id': user_id or '-', 'status': response.status_code,
                       'streaming': getattr(response, 'streaming', False)},
            )
        return response


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if not getattr(record, 'request_id', None) or record.request_id == '-':
            record.request_id = request_id_var.get()
        if not hasattr(record, 'user_id'):
            record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log search tools (set LOG_FORMAT=json)."""

    RESERVED = set(logging.makeLogRecord({}).__dict__) | {'message', 'asctime'}

    def format(self, record):
        payload = {
            'time': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
            'release': RELEASE,
        }
        for key, value in record.__dict__.items():
            if key not in self.RESERVED and key not in payload and not key.startswith('_'):
                payload[key] = value
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


RELEASE = (os.getenv('APP_RELEASE') or os.getenv('RENDER_GIT_COMMIT') or 'dev')[:40]


def run_in_context(target):
    """Wrap a thread target so it runs with the caller's logging context."""
    context = contextvars.copy_context()
    return lambda *args, **kwargs: context.run(target, *args, **kwargs)


def init_sentry(dsn, *, environment, traces_sample_rate=0.0):
    """Error tracking, when SENTRY_DSN is set. Sends no request bodies, cookies, headers
    or user details: only the stack trace, the request id and the pseudonymous user id."""
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:  # pragma: no cover - the dependency is in requirements.txt
        logging.getLogger(__name__).warning('SENTRY_DSN is set but sentry-sdk is missing.')
        return False

    def scrub(event, hint):
        request = event.get('request') or {}
        for key in ('data', 'cookies', 'headers', 'query_string', 'env'):
            request.pop(key, None)
        event['request'] = request
        event.pop('user', None)
        event.setdefault('tags', {})['request_id'] = request_id_var.get()
        event['tags']['user_id'] = user_id_var.get()
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=RELEASE,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size='never',
        traces_sample_rate=traces_sample_rate,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=scrub,
    )
    return True
