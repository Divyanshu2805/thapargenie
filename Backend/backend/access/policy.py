"""Access rules that live outside the auth apps."""

from chat.models import ChatSettings


def open_access_enabled():
    """True when admins have switched approval off: verified sign-ins get in directly."""
    return not ChatSettings.load().require_approval
