"""Access rules that live outside the auth apps."""

from chat.models import ChatSettings
from django.conf import settings


def open_access_domains():
    """Email domains that get in without approval; empty means any domain."""
    return tuple(domain.strip().lower().lstrip('@')
                 for domain in settings.OPEN_ACCESS_EMAIL_DOMAINS if domain.strip())


def email_domain_allowed(email):
    domains = open_access_domains()
    return not domains or (email or '').rpartition('@')[2].lower() in domains


def open_access_enabled(email=None):
    """True when admins have switched approval off and this address may get in directly.

    Addresses outside OPEN_ACCESS_EMAIL_DOMAINS keep waiting for an admin, who can still
    approve or invite them.
    """
    return not ChatSettings.load().require_approval and email_domain_allowed(email)
