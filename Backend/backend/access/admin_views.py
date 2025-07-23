"""Admin API for invitations, user eligibility and the audit log."""

from datetime import timedelta

from api.models import AuditEvent
from api.pagination import BoundedCursorPagination
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
from rest_framework.response import Response
from userauths.models import EligibilityState, IdentityInvitation, User

from access import services
from access.admin_serializers import (
    AuditEventSerializer,
    EligibilitySerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    UserSerializer,
)

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
