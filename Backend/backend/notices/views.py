"""Student notices API."""

import logging

from chat.schema import UrlOut
from common.admin_api import choice_param, error_response
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from knowledge.models import Category
from knowledge.storage import StorageError, get_storage
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from notices import services
from notices.serializers import (
    NoticeListOut,
    OfficialNoticeListOut,
    notice_payload,
    official_payload,
)

logger = logging.getLogger(__name__)

TAGS = ['notices']
DEFAULT_OFFICIAL_DAYS = 30


def _days(request):
    value = request.query_params.get('days') or str(DEFAULT_OFFICIAL_DAYS)
    if not value.isdigit() or not 1 <= int(value) <= services.MAX_OFFICIAL_DAYS:
        raise ValidationError({'days': [f'Use a number from 1 to {services.MAX_OFFICIAL_DAYS}.']})
    return int(value)


class NoticeListView(APIView):
    @extend_schema(operation_id='notices_list', tags=TAGS,
                   parameters=[OpenApiParameter('category', str, enum=Category.values)],
                   responses=NoticeListOut)
    def get(self, request):
        notices = services.student_notices(
            category=choice_param(request, 'category', Category.values)
        )
        return Response({'results': [notice_payload(notice) for notice in notices]})


class OfficialNoticeListView(APIView):
    @extend_schema(operation_id='notices_official_list', tags=TAGS,
                   parameters=[OpenApiParameter('days', int, default=DEFAULT_OFFICIAL_DAYS)],
                   responses=OfficialNoticeListOut)
    def get(self, request):
        documents = services.official_documents(_days(request))[:services.OFFICIAL_LIMIT]
        return Response({'results': [official_payload(document) for document in documents]})


class OfficialNoticeOpenView(APIView):
    @extend_schema(operation_id='notices_official_open', tags=TAGS,
                   responses=UrlOut)
    def get(self, request, document_id):
        document = services.official_documents(services.MAX_OFFICIAL_DAYS).filter(
            pk=document_id
        ).first()
        if document is None:
            raise Http404
        if document.source_url:
            return Response({'url': document.source_url})
        if not document.storage_path:
            raise Http404
        try:
            url = get_storage().signed_url(
                document.storage_path, filename=document.original_filename or None
            )
        except StorageError:
            logger.warning('Could not sign a link for notice document %s', document.pk,
                           exc_info=True)
            return error_response(request, status.HTTP_503_SERVICE_UNAVAILABLE,
                                  'source_unavailable', 'The file is unavailable right now.')
        return Response({'url': url})
