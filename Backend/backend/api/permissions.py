"""Explicit permissions for identity-sensitive API surfaces."""

import time

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from userauths.models import EligibilityState

from api.identity import FirebaseIdentity


class HasVerifiedEligibleIdentity(BasePermission):
    def has_permission(self, request, view):
        identity = request.auth
        if not isinstance(identity, FirebaseIdentity) or not identity.email_verified:
            raise PermissionDenied(
                'Email verification is required.', code='email_verification_required'
            )
        if request.user.eligibility_state != EligibilityState.APPROVED:
            raise PermissionDenied(
                'This account is not approved for student access.',
                code='eligibility_required',
            )
        return True


class HasRecentFirebaseAuthentication(BasePermission):
    def has_permission(self, request, view):
        identity = request.auth
        if not isinstance(identity, FirebaseIdentity):
            raise PermissionDenied('Firebase authentication is required.', code='firebase_required')
        age_seconds = int(time.time()) - identity.auth_time
        if age_seconds < 0 or age_seconds > settings.FIREBASE_RECENT_AUTH_SECONDS:
            raise PermissionDenied(
                'Recent sign-in is required for this action.', code='recent_auth_required'
            )
        return True
