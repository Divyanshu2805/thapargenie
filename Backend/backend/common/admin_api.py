"""Shared base for the admin API."""

import re

from api.pagination import BoundedCursorPagination
from api.permissions import HasRecentFirebaseAuthentication, HasVerifiedEligibleIdentity
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import AdminWriteThrottle


class AdminAPIView(APIView):
    """Staff only; every DELETE also needs a recent sign-in."""

    permission_classes = [IsAuthenticated, HasVerifiedEligibleIdentity, IsAdminUser]

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.request.method == 'DELETE':
            permissions.append(HasRecentFirebaseAuthentication())
        return permissions

    def get_throttles(self):
        return [*super().get_throttles(), AdminWriteThrottle()]


class NewestFirstPagination(BoundedCursorPagination):
    ordering = ('-created_at', '-id')


def request_id(request):
    return getattr(request, 'request_id', None)


def choice_param(request, name, choices):
    """A query filter that must be one of `choices`; None when absent or empty."""
    value = request.query_params.get(name)
    if not value:
        return None
    if value not in choices:
        raise ValidationError({name: [f'Use one of: {", ".join(choices)}.']})
    return value


def pattern_param(request, name, pattern, max_length):
    """A free-text query filter checked against a regex; None when absent or empty."""
    value = request.query_params.get(name)
    if not value:
        return None
    if len(value) > max_length or not re.fullmatch(pattern, value):
        raise ValidationError({name: ['This value is not valid.']})
    return value


def error_response(request, status, code, message, **extra):
    """The standard error envelope, for errors that carry more than a message."""
    error = {'code': code, 'message': message, 'request_id': request_id(request), **extra}
    return Response({'error': error}, status=status)


def paginate(view, queryset, serialize, pagination_class=NewestFirstPagination):
    paginator = pagination_class()
    page = paginator.paginate_queryset(queryset, view.request, view=view)
    return paginator.get_paginated_response([serialize(item) for item in page])
