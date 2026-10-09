from django.core.cache import caches
from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class InMemory:
    """Counts requests in this process's memory (the "throttle" cache, see settings).

    DRF's own throttles use the default cache, which here is the database: 6 statements
    on every request. The price of memory is that each worker counts separately.
    """

    cache = caches['throttle']


class UserThrottle(InMemory, UserRateThrottle):
    """The default for every view: a general per-user (or per-address) request limit."""

    scope = 'user'


class AskThrottle(InMemory, UserRateThrottle):
    """Limits how fast one user can send questions."""

    scope = 'ask'


class SuggestThrottle(InMemory, UserRateThrottle):
    """Follow-up suggestions: an AI call each, but only on request."""

    scope = 'suggest'


class AdminWriteThrottle(InMemory, UserRateThrottle):
    """Limits admin mutations; reads are not counted."""

    scope = 'admin_write'

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class ExportThrottle(InMemory, UserRateThrottle):
    """A full export is the most expensive student request."""

    scope = 'export'


class AdminExportThrottle(InMemory, UserRateThrottle):
    """CSV downloads: each one reads up to 5,000 rows."""

    scope = 'admin_export'


class SiteFeedbackThrottle(InMemory, UserRateThrottle):
    """Feedback on the site: a few per hour is plenty, and it keeps the admin queue clean."""

    scope = 'site_feedback'


class SharedViewThrottle(InMemory, AnonRateThrottle):
    """Public shared-answer links, counted per address (nobody is signed in there)."""

    scope = 'shared_view'


class ClientErrorThrottle(InMemory, UserRateThrottle):
    """Browser error reports; anonymous reporters are counted per address."""

    scope = 'client_error'
