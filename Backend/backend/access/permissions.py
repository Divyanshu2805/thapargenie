"""The second sign-in step for the admin API."""

from api.identity import FirebaseIdentity
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from access import two_factor
from access.models import SecondFactor


class HasSecondFactor(BasePermission):
    """This sign-in has passed two-factor (when STAFF_TWO_FACTOR_REQUIRED is on)."""

    def has_permission(self, request, view):
        if not settings.STAFF_TWO_FACTOR_REQUIRED:
            return True
        identity = request.auth
        if not isinstance(identity, FirebaseIdentity):
            raise PermissionDenied('Firebase authentication is required.', code='firebase_required')
        if two_factor.session_valid(request.user, identity.auth_time):
            return True
        enrolled = SecondFactor.objects.filter(
            user=request.user, confirmed_at__isnull=False
        ).exists()
        if enrolled:
            raise PermissionDenied('Enter the code from your authenticator app.',
                                   code='second_factor_required')
        raise PermissionDenied('Set up two-factor sign-in to use the admin dashboard.',
                               code='second_factor_setup_required')
