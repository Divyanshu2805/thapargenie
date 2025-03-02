"""DRF exception handling around the auth app's error envelope (`api.errors`, unchanged).

Adds what an operator needs and the envelope must not show: the full traceback of
every 5xx in the logs, a log line for refused and throttled requests, and an audit
event when a signed-in user is refused somewhere that matters.
"""

import logging

from api.errors import api_exception_handler
from rest_framework import exceptions

from common.audit import audit_denied

logger = logging.getLogger('thapargpt.errors')

# Refusals worth an audit event: probing the admin API, or a sensitive action attempted
# without a recent sign-in. Ordinary 404s and validation errors are not security events.
AUDITED_CODES = {'recent_auth_required', 'identity_review_required'}
ADMIN_PREFIX = '/api/v1/admin/'


def _code(exc):
    codes = exc.get_codes() if hasattr(exc, 'get_codes') else None
    return codes if isinstance(codes, str) else getattr(exc, 'default_code', 'error')


def exception_handler(exc, context):
    response = api_exception_handler(exc, context)
    request = context.get('request')
    path = getattr(request, 'path', '')
    method = getattr(request, 'method', '')
    status = response.status_code if response is not None else 500

    if status >= 500:
        logger.error('Server error on %s %s: %s', method, path, type(exc).__name__,
                     exc_info=(type(exc), exc, exc.__traceback__))
    elif isinstance(exc, exceptions.Throttled):
        logger.warning('Throttled %s %s (retry in %ss)', method, path, exc.wait)
    elif isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        logger.info('Authentication refused on %s %s: %s', method, path, _code(exc))
    elif isinstance(exc, exceptions.PermissionDenied):
        code = _code(exc)
        logger.warning('Permission denied on %s %s: %s', method, path, code)
        user = getattr(request, 'user', None)
        if getattr(user, 'is_authenticated', False) and (
            path.startswith(ADMIN_PREFIX) or code in AUDITED_CODES
        ):
            audit_denied(user, path=path, method=method, code=code,
                         request_id=getattr(request, 'request_id', None))
    return response
