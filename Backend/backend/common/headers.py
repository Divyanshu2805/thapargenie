"""Response headers for an API that only serves data (JSON and event streams).

Nothing the API returns should ever run as a page, so the policy forbids everything.
The Swagger UI and the Django admin render real HTML and keep Django's defaults.
"""

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
HTML_PATHS = ('/api/v1/docs/', '/admin/')


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', PERMISSIONS_POLICY)
        if not request.path.startswith(HTML_PATHS):
            response.setdefault('Content-Security-Policy', API_CSP)
        return response
