from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import UserRateThrottle


class AskThrottle(UserRateThrottle):
    """Limits how fast one user can send questions."""

    scope = 'ask'


class SuggestThrottle(UserRateThrottle):
    """Follow-up suggestions: an AI call each, but only on request."""

    scope = 'suggest'


class AdminWriteThrottle(UserRateThrottle):
    """Limits admin mutations; reads are not counted."""

    scope = 'admin_write'

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class ExportThrottle(UserRateThrottle):
    """A full export is the most expensive student request."""

    scope = 'export'
