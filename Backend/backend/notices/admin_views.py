"""Admin notices API."""

import logging

from api.pagination import BoundedCursorPagination
from common.admin_api import AdminAPIView, choice_param, error_response, paginate, request_id
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from knowledge import services as knowledge
from knowledge.errors import StorageUnavailable, UnsupportedFileError
from knowledge.ingest.filetypes import UnsupportedFile
from knowledge.storage import StorageError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from notices import services
from notices.models import Notice
from notices.serializers import AdminNoticeOut, NoticeWriteSerializer, admin_notice_payload

logger = logging.getLogger(__name__)

TAGS = ['admin: notices']
MAX_SEARCH_CHARS = 100


class _Ordered(BoundedCursorPagination):
    ordering = ('-publish_at', '-id')


class _Upcoming(BoundedCursorPagination):
    ordering = ('publish_at', 'id')


class _Edited(BoundedCursorPagination):
    ordering = ('-updated_at', '-id')


PAGINATION = {
    Notice.State.PUBLISHED: _Ordered,
    Notice.State.SCHEDULED: _Upcoming,
    Notice.State.DRAFT: _Edited,
    Notice.State.EXPIRED: _Ordered,
}


def _run(request, call):
    """Map knowledge-base failures from the copy sync to API errors."""
    try:
        return call()
    except knowledge.DuplicateDocument as exc:
        return error_response(
            request, status.HTTP_409_CONFLICT, 'duplicate_document',
            f'The knowledge base already has this exact text ("{exc.existing.title}"). '
            'Change the notice, or turn off "ThaparGenie can answer from this".',
            existing_id=str(exc.existing.pk),
        )
    except UnsupportedFile as exc:
        raise UnsupportedFileError(str(exc)) from exc
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, 'error_dict') else exc.messages)\
            from exc
    except StorageError as exc:
        logger.warning('Storage failure while syncing a notice', exc_info=True)
        raise StorageUnavailable() from exc


def _queryset():
    return Notice.objects.select_related('document', 'created_by', 'updated_by')


def _payload(notice):
    return admin_notice_payload(_queryset().get(pk=notice.pk))


class NoticeListView(AdminAPIView):
    @extend_schema(
        operation_id='admin_notices_list', tags=TAGS,
        parameters=[
            OpenApiParameter('state', str, enum=Notice.State.values, default='published'),
            OpenApiParameter('q', str),
        ],
        responses=AdminNoticeOut(many=True),
    )
    def get(self, request):
        state = choice_param(request, 'state', Notice.State.values) or Notice.State.PUBLISHED
        notices = _queryset().in_state(state)
        query = (request.query_params.get('q') or '').strip()[:MAX_SEARCH_CHARS]
        if query:
            notices = notices.filter(Q(title__icontains=query) | Q(body__icontains=query))
        now = timezone.now()
        return paginate(self, notices, lambda notice: admin_notice_payload(notice, now),
                        PAGINATION[state])

    @extend_schema(operation_id='admin_notices_create', tags=TAGS,
                   request=NoticeWriteSerializer, responses={201: AdminNoticeOut})
    def post(self, request):
        serializer = NoticeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = _run(request, lambda: services.create_notice(
            serializer.validated_data, user=request.user, request_id=request_id(request),
        ))
        if isinstance(result, Response):
            return result
        return Response(_payload(result), status=status.HTTP_201_CREATED)


class NoticeDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_notices_retrieve', tags=TAGS, responses=AdminNoticeOut)
    def get(self, request, notice_id):
        return Response(admin_notice_payload(get_object_or_404(_queryset(), pk=notice_id)))

    @extend_schema(operation_id='admin_notices_update', tags=TAGS,
                   request=NoticeWriteSerializer, responses=AdminNoticeOut)
    def patch(self, request, notice_id):
        notice = get_object_or_404(Notice, pk=notice_id)
        serializer = NoticeWriteSerializer(notice, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        result = _run(request, lambda: services.update_notice(
            notice, serializer.validated_data, user=request.user, request_id=request_id(request),
        ))
        if isinstance(result, Response):
            return result
        return Response(_payload(result))

    @extend_schema(
        operation_id='admin_notices_delete', tags=TAGS,
        parameters=[OpenApiParameter(
            'delete_document', bool, default=False,
            description='Also delete its knowledge-base copy; otherwise it is kept, not current.',
        )],
        responses={204: None},
    )
    def delete(self, request, notice_id):
        notice = get_object_or_404(Notice.objects.select_related('document'), pk=notice_id)
        delete_document = choice_param(request, 'delete_document', ('true', 'false')) == 'true'
        result = _run(request, lambda: services.delete_notice(
            notice, delete_document=delete_document, user=request.user,
            request_id=request_id(request),
        ))
        if isinstance(result, Response):
            return result
        return Response(status=status.HTTP_204_NO_CONTENT)
