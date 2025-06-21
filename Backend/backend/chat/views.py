"""Student chat API. Every query is scoped to request.user."""

import json
import logging

from api.permissions import HasRecentFirebaseAuthentication
from common.admin_api import error_response, request_id
from common.audit import audit
from common.sse import event_stream_response
from common.throttles import (
    AskThrottle,
    ExportThrottle,
)
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from knowledge.storage import StorageError, get_storage
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from chat import answering, engine, quota
from chat.models import (
    ChatSettings,
    Conversation,
    Feedback,
    Message,
    MessageSource,
)
from chat.schema import (
    EVENT_STREAM,
    AppConfigOut,
    ConversationListOut,
    FeedbackOut,
    MessagesOut,
    UrlOut,
)
from chat.serializers import (
    AskSerializer,
    ConversationCreateSerializer,
    ConversationSerializer,
    ConversationUpdateSerializer,
    FeedbackSerializer,
    RegenerateSerializer,
    feedback_payload,
    message_payload,
    search_snippet,
    source_payload,
)

logger = logging.getLogger(__name__)

MIN_SEARCH_CHARS = 2


class ConversationPagination(CursorPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = ('-last_message_at', '-id')


def _bool_param(request, name):
    value = request.query_params.get(name)
    if value is None:
        return None
    return value.lower() in ('1', 'true', 'yes')


def owned_conversation(request, conversation_id, *, lock=False):
    return get_object_or_404(Conversation.objects.owned_by(request.user), pk=conversation_id)


def owned_message(request, message_id):
    return get_object_or_404(
        Message.objects.select_related('conversation'),
        pk=message_id,
        conversation__user=request.user,
    )


class ConversationListView(APIView):
    def get_permissions(self):
        permissions = super().get_permissions()
        # Deleting every conversation is irreversible: ask for a recent sign-in.
        if self.request.method == 'DELETE':
            permissions.append(HasRecentFirebaseAuthentication())
        return permissions

    @extend_schema(
        operation_id='conversations_list',
        tags=['chat'],
        parameters=[
            OpenApiParameter('archived', bool),
            OpenApiParameter('pinned', bool),
            OpenApiParameter('q', str, description=(
                'Search in titles and in every message (questions and answers); at least '
                f'{MIN_SEARCH_CHARS} characters. Results carry `match` with a snippet.')),
        ],
        responses=ConversationListOut(many=True),
    )
    def get(self, request):
        conversations = Conversation.objects.owned_by(request.user).filter(
            is_archived=bool(_bool_param(request, 'archived'))
        )
        pinned = _bool_param(request, 'pinned')
        if pinned is not None:
            conversations = conversations.filter(is_pinned=pinned)
        query = ' '.join((request.query_params.get('q') or '').split())[:100]
        searching = len(query) >= MIN_SEARCH_CHARS
        if searching:
            # The newest message in each conversation that contains the words.
            hits = Message.objects.filter(conversation=OuterRef('pk'),
                                          content__icontains=query).order_by('-created_at')
            conversations = conversations.annotate(
                match_role=Subquery(hits.values('role')[:1]),
                match_content=Subquery(hits.values('content')[:1]),
            ).filter(Q(title__icontains=query) | Q(match_role__isnull=False))
        paginator = ConversationPagination()
        page = paginator.paginate_queryset(conversations, request, view=self)
        data = ConversationSerializer(page, many=True).data
        if searching:
            for item, conversation in zip(data, page, strict=True):
                item['match'] = {
                    'role': conversation.match_role,
                    'snippet': search_snippet(conversation.match_content, query),
                } if conversation.match_role else None
        return paginator.get_paginated_response(data)

    @extend_schema(operation_id='conversations_create', tags=['chat'],
                   request=ConversationCreateSerializer, responses={201: ConversationSerializer})
    def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = ' '.join(serializer.validated_data.get('title', '').split())
        conversation = Conversation.objects.create(
            user=request.user,
            title=title,
            title_source=Conversation.TitleSource.USER if title else
            Conversation.TitleSource.AUTO,
        )
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)

    @extend_schema(operation_id='conversations_delete_all', tags=['chat'], responses={204: None})
    def delete(self, request):
        owned = Conversation.objects.owned_by(request.user)
        count = owned.count()
        owned.delete()
        audit(request.user, 'privacy.deleted_all', 'user', request.user.pk,
              request_id=request_id(request), conversations=count)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationDetailView(APIView):
    @extend_schema(operation_id='conversations_retrieve', tags=['chat'],
                   responses=ConversationSerializer)
    def get(self, request, conversation_id):
        return Response(ConversationSerializer(owned_conversation(request, conversation_id)).data)

    @extend_schema(operation_id='conversations_update', tags=['chat'],
                   request=ConversationUpdateSerializer, responses=ConversationSerializer)
    def patch(self, request, conversation_id):
        conversation = owned_conversation(request, conversation_id)
        serializer = ConversationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fields = []
        if 'title' in data:
            conversation.title = data['title']
            conversation.title_source = Conversation.TitleSource.USER
            fields += ['title', 'title_source']
        for flag in ('is_pinned', 'is_archived'):
            if flag in data:
                setattr(conversation, flag, data[flag])
                fields.append(flag)
        if fields:
            conversation.save(update_fields=[*fields, 'updated_at'])
        if 'current_leaf_id' in data and engine.switch_branch(
            conversation, data['current_leaf_id']
        ) is None:
            raise Http404
        return Response(ConversationSerializer(conversation).data)

    @extend_schema(operation_id='conversations_delete', tags=['chat'], responses={204: None})
    def delete(self, request, conversation_id):
        owned_conversation(request, conversation_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListView(APIView):
    """GET: the active branch. POST: ask a question (streams SSE)."""

    def get_throttles(self):
        throttles = super().get_throttles()
        return [*throttles, AskThrottle()] if self.request.method == 'POST' else throttles

    @extend_schema(operation_id='messages_list', tags=['chat'], responses=MessagesOut)
    def get(self, request, conversation_id):
        conversation = owned_conversation(request, conversation_id)
        engine.expire_stale_streams(conversation=conversation)
        path, tree = engine.active_path(conversation)
        ids = [message.pk for message in path]
        sources, feedback = {}, {}
        for source in MessageSource.objects.filter(message_id__in=ids).select_related('document'):
            sources.setdefault(source.message_id, []).append(source)
        for item in Feedback.objects.filter(message_id__in=ids):
            feedback[item.message_id] = item
        messages = [
            message_payload(
                message,
                siblings=tree.siblings(message),
                sources=sorted(sources.get(message.pk, []), key=lambda s: s.position),
                feedback=feedback.get(message.pk),
            )
            for message in path
        ]
        return Response({
            'conversation': ConversationSerializer(conversation).data,
            'messages': messages,
        })

    @extend_schema(operation_id='messages_ask', tags=['chat'], request=AskSerializer,
                   responses={200: EVENT_STREAM})
    def post(self, request, conversation_id):
        conversation = owned_conversation(request, conversation_id)
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        turn = answering.start_turn(
            request.user,
            conversation,
            content=data['content'],
            client_request_id=data['client_request_id'],
        )
        return event_stream_response(answering.stream_turn(turn))


class RegenerateView(APIView):
    throttle_classes = [AskThrottle]

    @extend_schema(operation_id='messages_regenerate', tags=['chat'],
                   request=RegenerateSerializer, responses={200: EVENT_STREAM})
    def post(self, request, message_id):
        message = owned_message(request, message_id)
        serializer = RegenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        turn = answering.start_turn(
            request.user,
            message.conversation,
            client_request_id=serializer.validated_data['client_request_id'],
            regenerate=message,
        )
        return event_stream_response(answering.stream_turn(turn))


class FeedbackView(APIView):
    @extend_schema(operation_id='feedback_set', tags=['chat'], request=FeedbackSerializer,
                   responses=FeedbackOut)
    def put(self, request, message_id):
        message = owned_message(request, message_id)
        if message.role != Message.Role.ASSISTANT or message.status != Message.Status.COMPLETE:
            raise Http404
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        feedback, _ = Feedback.objects.update_or_create(
            message=message,
            defaults={
                'user': request.user,
                'rating': data['rating'],
                'reason': data.get('reason') if data['rating'] < 0 else None,
                'comment': data.get('comment', ''),
            },
        )
        return Response(feedback_payload(feedback))

    @extend_schema(operation_id='feedback_delete', tags=['chat'], responses={204: None})
    def delete(self, request, message_id):
        message = owned_message(request, message_id)
        Feedback.objects.filter(message=message).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SourceOpenView(APIView):
    @extend_schema(operation_id='sources_open', tags=['chat'], responses=UrlOut)
    def get(self, request, source_id):
        source = get_object_or_404(
            MessageSource.objects.select_related('document'),
            pk=source_id,
            message__conversation__user=request.user,
        )
        if source.url:
            return Response({'url': source.url})
        document = source.document
        if document is None or not document.storage_path:
            raise Http404
        try:
            url = get_storage().signed_url(
                document.storage_path, filename=document.original_filename or None
            )
        except StorageError:
            logger.warning('Could not sign a link for source %s', source.pk, exc_info=True)
            return error_response(request, status.HTTP_503_SERVICE_UNAVAILABLE,
                                  'source_unavailable', 'The source file is unavailable right now.')
        return Response({'url': url})


class AppConfigView(APIView):
    @extend_schema(operation_id='app_config', tags=['chat'], responses=AppConfigOut)
    def get(self, request):
        settings = ChatSettings.load()
        return Response({
            'starter_questions': settings.starter_questions,
            'daily_limit': None if request.user.is_staff else settings.daily_question_limit,
            'remaining_today': quota.remaining(request.user),
        })


class ExportView(APIView):
    """Everything the student has said and received, as a JSON download."""

    throttle_classes = [ExportThrottle]

    @extend_schema(operation_id='me_export', tags=['me'],
                   responses={(200, 'application/json'): OpenApiTypes.OBJECT})
    def get(self, request):
        conversations = Conversation.objects.owned_by(request.user).prefetch_related(
            Prefetch('messages', queryset=Message.objects.order_by('created_at')),
            'messages__sources__document',
        )
        data = {
            'exported_at': timezone.now().isoformat(),
            'email': request.user.email,
            'conversations': [
                {
                    'id': str(conversation.pk),
                    'title': conversation.title,
                    'created_at': conversation.created_at.isoformat(),
                    'messages': [
                        {
                            'id': str(message.pk),
                            'parent_id': str(message.parent_id) if message.parent_id else None,
                            'role': message.role,
                            'content': message.content,
                            'status': message.status,
                            'created_at': message.created_at.isoformat(),
                            'sources': [source_payload(s) for s in message.sources.all()],
                        }
                        for message in conversation.messages.all()
                    ],
                }
                for conversation in conversations
            ],
        }
        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8',
        )
        response['Content-Disposition'] = 'attachment; filename="thapargpt-export.json"'
        audit(request.user, 'privacy.exported', 'user', request.user.pk,
              request_id=request_id(request), conversations=len(data['conversations']))
        return response
