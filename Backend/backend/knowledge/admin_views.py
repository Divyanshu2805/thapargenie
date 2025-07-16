"""Admin API for the knowledge base. Views validate and call services."""

import logging

from chat.models import ChatSettings
from common.admin_api import AdminAPIView, choice_param, error_response, paginate, request_id
from common.audit import audit
from common.safe_http import UnsafeURLError
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from knowledge import services
from knowledge.admin_serializers import (
    DocumentSerializer,
    DocumentUpdateSerializer,
    FileUrlSerializer,
    ReprocessSerializer,
    TextDocumentSerializer,
    UploadResultSerializer,
    UploadSchema,
    UploadSerializer,
    UrlDocumentSerializer,
)
from knowledge.errors import (
    FileTooLarge,
    InvalidTransitionError,
    StorageUnavailable,
    TooManyFiles,
    UnsupportedFileError,
    UrlNotAllowed,
)
from knowledge.ingest.filetypes import UnsupportedFile
from knowledge.models import Category, Document, DocumentStatus, SourceType
from knowledge.storage import StorageError, get_storage

logger = logging.getLogger(__name__)

MAX_FILES = 10
TAGS = ['admin: knowledge']


def _max_file_bytes():
    return settings.INGEST_MAX_FILE_MB * 1024 * 1024


def _meta(validated):
    meta = dict(validated)
    if 'contextualize' not in meta:
        meta['contextualize'] = ChatSettings.load().contextualize_default
    return meta


def _duplicate(request, exc):
    return error_response(
        request, status.HTTP_409_CONFLICT, 'duplicate_document', str(exc),
        existing_id=str(exc.existing.pk),
    )


def _run(call):
    """Map service exceptions to API errors."""
    try:
        return call()
    except UnsupportedFile as exc:
        raise UnsupportedFileError(str(exc)) from exc
    except UnsafeURLError as exc:
        raise UrlNotAllowed() from exc
    except services.InvalidTransition as exc:
        raise InvalidTransitionError(str(exc)) from exc
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, 'error_dict') else exc.messages)\
            from exc
    except StorageError as exc:
        logger.warning('Storage failure in the knowledge admin API', exc_info=True)
        raise StorageUnavailable() from exc


def _document(document_id):
    return get_object_or_404(Document, pk=document_id)


FILTER_PARAMETERS = [
    OpenApiParameter('status', str, enum=DocumentStatus.values),
    OpenApiParameter('category', str, enum=Category.values),
    OpenApiParameter('source_type', str, enum=SourceType.values),
    OpenApiParameter('q', str, description='Search in titles.'),
]


def filtered_documents(request):
    """The documents list's filters; shared with the ids endpoint so both always agree."""
    documents = Document.objects.all()
    filters = {'status': DocumentStatus, 'category': Category, 'source_type': SourceType}
    for name, choices in filters.items():
        if value := choice_param(request, name, choices.values):
            documents = documents.filter(**{name: value})
    query = (request.query_params.get('q') or '').strip()[:100]
    if query:
        documents = documents.filter(title__icontains=query)
    return documents


class DocumentListView(AdminAPIView):
    def get_parsers(self):
        if self.request is not None and self.request.method == 'POST':
            return [MultiPartParser()]
        return super().get_parsers()

    @extend_schema(operation_id='admin_documents_list', tags=TAGS,
                   parameters=FILTER_PARAMETERS, responses=DocumentSerializer(many=True))
    def get(self, request):
        return paginate(self, filtered_documents(request), lambda d: DocumentSerializer(d).data)

    @extend_schema(
        operation_id='admin_documents_upload',
        tags=TAGS,
        request={'multipart/form-data': UploadSchema},
        responses={202: UploadResultSerializer},
    )
    def post(self, request):
        # Refuse oversized bodies before Django spools them to disk.
        limit = MAX_FILES * _max_file_bytes() + 1024 * 1024
        if int(request.META.get('CONTENT_LENGTH') or 0) > limit:
            raise FileTooLarge()
        files = request.FILES.getlist('files')
        if not files:
            raise ValidationError({'files': ['Attach at least one file.']})
        if len(files) > MAX_FILES:
            raise TooManyFiles()
        fields = {key: request.data.get(key) for key in request.data if key != 'files'}
        serializer = UploadSerializer(data=fields)
        serializer.is_valid(raise_exception=True)
        meta = _meta(serializer.validated_data)
        if len(files) > 1:
            meta.pop('title', None)

        created, rejected = [], []
        for upload in files:
            failure = self._add_file(request, upload, meta, created)
            if failure is not None:
                rejected.append(failure)
        statuses = [item.pop('status') for item in rejected]
        if not created:
            return error_response(request, statuses[0], **rejected[0])
        return Response(
            {'created': DocumentSerializer(created, many=True).data, 'rejected': rejected},
            status=status.HTTP_202_ACCEPTED,
        )

    def _add_file(self, request, upload, meta, created):
        """Queue one file; return a rejection (with its HTTP status) or None."""
        filename = (upload.name or 'upload')[:255]
        if upload.size > _max_file_bytes():
            return {'filename': filename, 'code': 'file_too_large', 'status': 413,
                    'message': f'Files are limited to {settings.INGEST_MAX_FILE_MB} MB.'}
        file_meta = {**meta}
        title = file_meta.pop('title', None)
        if title:
            file_meta['title'] = title
        try:
            document = _run(lambda: services.create_from_upload(
                data=upload.read(), filename=filename, meta=file_meta, user=request.user,
                request_id=request_id(request),
            ))
        except services.DuplicateDocument as exc:
            return {'filename': filename, 'code': 'duplicate_document', 'status': 409,
                    'message': str(exc), 'existing_id': str(exc.existing.pk)}
        except (UnsupportedFileError, ValidationError, StorageUnavailable) as exc:
            detail = exc.detail if isinstance(exc.detail, str) else \
                'The file metadata is invalid.'
            return {'filename': filename, 'code': exc.default_code, 'message': str(detail),
                    'status': exc.status_code}
        created.append(document)
        return None


class DocumentFromUrlView(AdminAPIView):
    @extend_schema(operation_id='admin_documents_add_url', tags=TAGS,
                   request=UrlDocumentSerializer, responses={202: DocumentSerializer})
    def post(self, request):
        serializer = UrlDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meta = _meta(serializer.validated_data)
        url = meta.pop('url')
        try:
            document = _run(lambda: services.create_from_url(
                url=url, meta=meta, user=request.user, request_id=request_id(request),
            ))
        except services.DuplicateDocument as exc:
            return _duplicate(request, exc)
        return Response(DocumentSerializer(document).data, status=status.HTTP_202_ACCEPTED)


class DocumentFromTextView(AdminAPIView):
    @extend_schema(operation_id='admin_documents_add_text', tags=TAGS,
                   request=TextDocumentSerializer, responses={202: DocumentSerializer})
    def post(self, request):
        serializer = TextDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meta = _meta(serializer.validated_data)
        title, text = meta.pop('title'), meta.pop('text')
        try:
            document = _run(lambda: services.create_from_text(
                title=title, text=text, meta=meta, user=request.user,
                request_id=request_id(request),
            ))
        except services.DuplicateDocument as exc:
            return _duplicate(request, exc)
        return Response(DocumentSerializer(document).data, status=status.HTTP_202_ACCEPTED)


class DocumentDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_documents_retrieve', tags=TAGS,
                   responses=DocumentSerializer)
    def get(self, request, document_id):
        return Response(DocumentSerializer(_document(document_id)).data)

    @extend_schema(operation_id='admin_documents_update', tags=TAGS,
                   request=DocumentUpdateSerializer, responses=DocumentSerializer)
    def patch(self, request, document_id):
        document = _document(document_id)
        serializer = DocumentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = _run(lambda: services.update_document(
            document, serializer.validated_data, user=request.user,
            request_id=request_id(request),
        ))
        return Response(DocumentSerializer(document).data)

    @extend_schema(operation_id='admin_documents_delete', tags=TAGS, responses={204: None})
    def delete(self, request, document_id):
        document = _document(document_id)
        _run(lambda: services.delete_document(
            document, user=request.user, request_id=request_id(request)
        ))
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentReprocessView(AdminAPIView):
    @extend_schema(operation_id='admin_documents_reprocess', tags=TAGS,
                   request=ReprocessSerializer, responses={202: DocumentSerializer})
    def post(self, request, document_id):
        document = _document(document_id)
        serializer = ReprocessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = _run(lambda: services.reprocess(
            document, user=request.user, parser=serializer.validated_data.get('parser'),
            request_id=request_id(request),
        ))
        return Response(DocumentSerializer(document).data, status=status.HTTP_202_ACCEPTED)


class DocumentEnableView(AdminAPIView):
    enabled = True

    @extend_schema(tags=TAGS, request=None, responses=DocumentSerializer)
    def post(self, request, document_id):
        document = _document(document_id)
        document = _run(lambda: services.set_enabled(
            document, self.enabled, user=request.user, request_id=request_id(request)
        ))
        return Response(DocumentSerializer(document).data)


class DocumentDisableView(DocumentEnableView):
    enabled = False


class DocumentFileView(AdminAPIView):
    @extend_schema(operation_id='admin_documents_file', tags=TAGS, responses=FileUrlSerializer)
    def get(self, request, document_id):
        document = _document(document_id)
        if document.storage_path:
            filename = document.original_filename or None
            url = _run(lambda: get_storage().signed_url(document.storage_path,
                                                        filename=filename))
            audit(request.user, 'document.file_opened', 'document', document.pk,
                  request_id=request_id(request))
            return Response({'url': url})
        if document.source_url:
            return Response({'url': document.source_url})
        raise Http404
