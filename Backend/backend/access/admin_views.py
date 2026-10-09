"""Admin API for invitations, user eligibility and the audit log."""

from datetime import timedelta

from api.models import AuditEvent
from api.pagination import BoundedCursorPagination
from api.permissions import HasRecentFirebaseAuthentication, HasVerifiedEligibleIdentity
from common.admin_api import (
    AdminAPIView,
    choice_param,
    error_response,
    paginate,
    pattern_param,
    request_id,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from userauths.models import EligibilityState, IdentityInvitation, User

from access import services, two_factor
from access.admin_serializers import (
    AuditEventSerializer,
    EligibilitySerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    TwoFactorCodeSerializer,
    TwoFactorRecoveryCodesSerializer,
    TwoFactorSetupSerializer,
    TwoFactorStatusSerializer,
    TwoFactorVerifySerializer,
    UserSerializer,
)
from access.permissions import HasSecondFactor

TAGS = ['admin: access']
# Audit actions are dotted lowercase names ("document.deleted"); a trailing dot filters by prefix.
AUDIT_NAME = r'[a-z][a-z0-9_]*'
AUDIT_ACTION = rf'{AUDIT_NAME}(\.{AUDIT_NAME})*\.?'


class UserPagination(BoundedCursorPagination):
    ordering = ('-date_joined', '-id')


def _conflict(request, exc):
    return error_response(request, status.HTTP_409_CONFLICT, exc.code, str(exc))


def _search(request):
    return (request.query_params.get('q') or '').strip()[:100]


class InvitationListView(AdminAPIView):
    @extend_schema(operation_id='admin_invitations_list', tags=TAGS,
                   parameters=[OpenApiParameter('q', str, description='Search in emails.')],
                   responses=InvitationSerializer(many=True))
    def get(self, request):
        invitations = IdentityInvitation.objects.all()
        if query := _search(request):
            invitations = invitations.filter(email__icontains=query)
        return paginate(self, invitations, lambda i: InvitationSerializer(i).data)

    @extend_schema(operation_id='admin_invitations_create', tags=TAGS,
                   request=InvitationCreateSerializer, responses={201: InvitationSerializer})
    def post(self, request):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expires_at = None
        if 'expires_in_days' in data:
            expires_at = timezone.now() + timedelta(days=data['expires_in_days'])
        try:
            invitation = services.create_invitation(
                data['email'], actor=request.user, expires_at=expires_at,
                request_id=request_id(request),
            )
        except services.AccessError as exc:
            return _conflict(request, exc)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_invitations_delete', tags=TAGS, responses={204: None})
    def delete(self, request, invitation_id):
        invitation = get_object_or_404(IdentityInvitation, pk=invitation_id)
        try:
            services.delete_invitation(invitation, actor=request.user,
                                       request_id=request_id(request))
        except services.AccessError as exc:
            return _conflict(request, exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(AdminAPIView):
    @extend_schema(
        operation_id='admin_users_list',
        tags=TAGS,
        parameters=[
            OpenApiParameter('q', str, description='Search in emails and names.'),
            OpenApiParameter('eligibility_state', str, enum=EligibilityState.values),
        ],
        responses=UserSerializer(many=True),
    )
    def get(self, request):
        users = User.objects.all()
        if query := _search(request):
            users = users.filter(email__icontains=query) | users.filter(
                first_name__icontains=query) | users.filter(last_name__icontains=query)
        if state := choice_param(request, 'eligibility_state', EligibilityState.values):
            users = users.filter(eligibility_state=state)
        return paginate(self, users, lambda u: UserSerializer(u).data,
                        pagination_class=UserPagination)


class UserDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_users_update', tags=TAGS,
                   request=EligibilitySerializer, responses=UserSerializer)
    def patch(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        serializer = EligibilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            target = services.set_eligibility(
                target, data['eligibility_state'], actor=request.user,
                reason=' '.join(data.get('reason', '').split()),
                request_id=request_id(request),
            )
        except services.AccessError as exc:
            return _conflict(request, exc)
        return Response(UserSerializer(target).data)


class AuditLogView(AdminAPIView):
    @extend_schema(
        operation_id='admin_audit_log',
        tags=TAGS,
        parameters=[
            OpenApiParameter('action', str,
                             description='Exact action, or a prefix ending in "." '
                                         '(e.g. "document.").'),
            OpenApiParameter('resource_type', str),
            OpenApiParameter('resource_id', str),
        ],
        responses=AuditEventSerializer(many=True),
    )
    def get(self, request):
        events = AuditEvent.objects.select_related('actor')
        if action := pattern_param(request, 'action', AUDIT_ACTION, 100):
            events = events.filter(action__startswith=action) if action.endswith('.') \
                else events.filter(action=action)
        if resource_type := pattern_param(request, 'resource_type', AUDIT_NAME, 100):
            events = events.filter(resource_type=resource_type)
        if resource_id := pattern_param(request, 'resource_id', r'\S+', 128):
            events = events.filter(resource_id=resource_id)
        return paginate(self, events, lambda e: AuditEventSerializer(e).data)


class TwoFactorView(AdminAPIView):
    """The second sign-in step itself: open to staff who have not passed it yet."""

    permission_classes = [IsAuthenticated, HasVerifiedEligibleIdentity, IsAdminUser]

    def fail(self, exc):
        if exc.code == 'second_factor_locked':
            code = status.HTTP_429_TOO_MANY_REQUESTS
        elif exc.code == 'second_factor_invalid_code':
            code = status.HTTP_400_BAD_REQUEST
        else:
            code = status.HTTP_409_CONFLICT
        return error_response(self.request, code, exc.code, str(exc))

    def current(self):
        return two_factor.status(self.request.user, self.request.auth.auth_time)


class TwoFactorStatusView(TwoFactorView):
    @extend_schema(operation_id='admin_two_factor_status', tags=TAGS,
                   responses=TwoFactorStatusSerializer)
    def get(self, request):
        return Response(self.current())


class TwoFactorSetupView(TwoFactorView):
    @extend_schema(operation_id='admin_two_factor_setup', tags=TAGS, request=None,
                   responses=TwoFactorSetupSerializer)
    def post(self, request):
        try:
            return Response(two_factor.begin_setup(request.user))
        except two_factor.TwoFactorError as exc:
            return self.fail(exc)


class TwoFactorConfirmView(TwoFactorView):
    @extend_schema(operation_id='admin_two_factor_confirm', tags=TAGS,
                   request=TwoFactorCodeSerializer, responses=TwoFactorRecoveryCodesSerializer)
    def post(self, request):
        serializer = TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            codes = two_factor.confirm_setup(
                request.user, serializer.validated_data['code'], request.auth.auth_time,
                request_id=request_id(request),
            )
        except two_factor.TwoFactorError as exc:
            return self.fail(exc)
        return Response({'recovery_codes': codes, 'status': self.current()})


class TwoFactorVerifyView(TwoFactorView):
    @extend_schema(operation_id='admin_two_factor_verify', tags=TAGS,
                   request=TwoFactorVerifySerializer, responses=TwoFactorStatusSerializer)
    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            return Response(two_factor.verify(
                request.user, request.auth.auth_time, code=data.get('code', ''),
                recovery_code=data.get('recovery_code', ''), request_id=request_id(request),
            ))
        except two_factor.TwoFactorError as exc:
            return self.fail(exc)


class TwoFactorRecoveryCodesView(TwoFactorView):
    """New backup codes replace the old ones: needs the second step and a recent sign-in."""

    permission_classes = [*TwoFactorView.permission_classes, HasSecondFactor,
                          HasRecentFirebaseAuthentication]

    @extend_schema(operation_id='admin_two_factor_recovery_codes', tags=TAGS, request=None,
                   responses=TwoFactorRecoveryCodesSerializer)
    def post(self, request):
        try:
            codes = two_factor.regenerate_recovery_codes(request.user,
                                                         request_id=request_id(request))
        except two_factor.TwoFactorError as exc:
            return self.fail(exc)
        return Response({'recovery_codes': codes, 'status': self.current()})
