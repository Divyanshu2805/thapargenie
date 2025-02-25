"""Stable, non-sensitive API error responses."""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: 'invalid_request',
    status.HTTP_401_UNAUTHORIZED: 'unauthenticated',
    status.HTTP_403_FORBIDDEN: 'forbidden',
    status.HTTP_404_NOT_FOUND: 'not_found',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'method_not_allowed',
    status.HTTP_409_CONFLICT: 'conflict',
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: 'payload_too_large',
    status.HTTP_429_TOO_MANY_REQUESTS: 'rate_limited',
    status.HTTP_503_SERVICE_UNAVAILABLE: 'service_unavailable',
}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get('request')
    request_id = getattr(request, 'request_id', None)
    if response is None:
        logger.error(
            'Unhandled API exception type=%s',
            type(exc).__name__,
            extra={'request_id': request_id or '-'},
        )
        return Response(
            {
                'error': {
                    'code': 'internal_error',
                    'message': 'The request could not be completed.',
                    'request_id': request_id,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    error_codes = exc.get_codes() if hasattr(exc, 'get_codes') else None
    code = error_codes if isinstance(error_codes, str) else None
    code = code or getattr(exc, 'default_code', None) or STATUS_CODES.get(
        response.status_code, 'request_failed'
    )
    if isinstance(response.data, dict) and 'detail' not in response.data:
        detail = response.data
    else:
        detail = response.data.get('detail') if isinstance(response.data, dict) else response.data
    if isinstance(detail, (list, dict)):
        message = 'The request could not be processed.'
        fields = detail
    else:
        message = str(detail or 'The request could not be processed.')
        fields = None

    payload = {'error': {'code': str(code), 'message': message, 'request_id': request_id}}
    if fields:
        payload['error']['fields'] = fields
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        try:
            payload['error']['retry_after_seconds'] = int(retry_after)
        except ValueError:
            pass
    response.data = payload
    return response
