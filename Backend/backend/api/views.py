"""Operational and identity API views."""

import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from userauths.models import EligibilityState

from api.authentication import IdentityServiceUnavailable
from api.firebase import FirebaseIdentityUnavailable, revoke_firebase_sessions
from api.models import AuditEvent, AuditOutcome
from api.permissions import HasRecentFirebaseAuthentication, HasVerifiedEligibleIdentity
from api.serializers import MeUpdateSerializer

logger = logging.getLogger(__name__)


@require_GET
def service_index(request):
    return JsonResponse({'service': 'thapargenie-api'})


@require_GET
def health_live(request):
    return JsonResponse({'status': 'ok'})


@require_GET
def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        logger.warning('Readiness check failed: the database is unreachable', exc_info=True)
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ready'})


def _onboarding_status(user, identity):
    if not identity.email_verified:
        return 'email_verification_required'
    return {
        EligibilityState.PENDING: 'approval_pending',
        EligibilityState.APPROVED: 'ready',
        EligibilityState.DENIED: 'access_denied',
        EligibilityState.SUSPENDED: 'access_suspended',
    }[user.eligibility_state]


def _me_payload(request):
    profile = request.user.profile
    identity = request.auth
    return {
        'uid': identity.uid,
        'email': request.user.email,
        'email_verified': identity.email_verified,
        'eligibility_state': request.user.eligibility_state,
        'onboarding_status': _onboarding_status(request.user, identity),
        'is_staff': request.user.is_staff,
        'preferences': {
            'campus': profile.campus,
            'program': profile.program,
            'academic_year': profile.academic_year,
        },
    }


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        permissions = super().get_permissions()
        # Anyone signed in may read their onboarding status; only approved students edit.
        if self.request.method == 'PATCH':
            permissions.append(HasVerifiedEligibleIdentity())
        return permissions

    def get(self, request):
        return Response(_me_payload(request))

    def patch(self, request):
        serializer = MeUpdateSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_me_payload(request))


class RevokeSessionsView(APIView):
    permission_classes = [IsAuthenticated, HasRecentFirebaseAuthentication]

    def post(self, request):
        try:
            valid_after = revoke_firebase_sessions(request.auth.uid)
        except FirebaseIdentityUnavailable as exc:
            raise IdentityServiceUnavailable() from exc

        request.user.firebase_tokens_valid_after = valid_after
        request.user.save(update_fields=['firebase_tokens_valid_after'])
        AuditEvent.objects.create(
            actor=request.user,
            action='identity.sessions_revoked',
            resource_type='user',
            resource_id=str(request.user.pk),
            outcome=AuditOutcome.SUCCEEDED,
            request_id=getattr(request, 'request_id', None),
            metadata={'provider': 'firebase'},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
