"""Request correlation without trusting arbitrary client-provided identifiers."""

from uuid import UUID, uuid4


def _request_id(value):
    if not value:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


class RequestIDMiddleware:
    header_name = 'HTTP_X_REQUEST_ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = _request_id(request.META.get(self.header_name))
        response = self.get_response(request)
        response['X-Request-ID'] = request.request_id
        return response
