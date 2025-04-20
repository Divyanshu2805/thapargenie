"""Student chat API. Every query is scoped to request.user."""

import logging

from common.sse import event_stream_response
from common.throttles import (
    AskThrottle,
)
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from chat import answering, quota
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
    MessagesOut,
)
from chat.serializers import (
    AskSerializer,
    ConversationCreateSerializer,
    ConversationSerializer,
    ConversationUpdateSerializer,
    message_payload,
)

logger = logging.getLogger(__name__)


class ConversationPagination(CursorPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = ('-last_message_at', '-id')


def owned_conversation(request, conversation_id, *, lock=False):
    return get_object_or_404(Conversation.objects.owned_by(request.user), pk=conversation_id)


def owned_message(request, message_id):
    return get_object_or_404(
        Message.objects.select_related('conversation'),
        pk=message_id,
        conversation__user=request.user,
    )


class ConversationListView(APIView):
    @extend_schema(operation_id='conversations_list', tags=['chat'],
                   responses=ConversationSerializer(many=True))
    def get(self, request):
        conversations = Conversation.objects.owned_by(request.user)
        paginator = ConversationPagination()
        page = paginator.paginate_queryset(conversations, request, view=self)
        data = ConversationSerializer(page, many=True).data
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
        if fields:
            conversation.save(update_fields=[*fields, 'updated_at'])
        return Response(ConversationSerializer(conversation).data)

    @extend_schema(operation_id='conversations_delete', tags=['chat'], responses={204: None})
    def delete(self, request, conversation_id):
        owned_conversation(request, conversation_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListView(APIView):
    """GET: the thread. POST: ask a question (streams SSE)."""

    def get_throttles(self):
        throttles = super().get_throttles()
        return [*throttles, AskThrottle()] if self.request.method == 'POST' else throttles

    @extend_schema(operation_id='messages_list', tags=['chat'], responses=MessagesOut)
    def get(self, request, conversation_id):
        conversation = owned_conversation(request, conversation_id)
        path = list(conversation.messages.order_by('created_at', 'id'))
        ids = [message.pk for message in path]
        sources, feedback = {}, {}
        for source in MessageSource.objects.filter(message_id__in=ids).select_related('document'):
            sources.setdefault(source.message_id, []).append(source)
        for item in Feedback.objects.filter(message_id__in=ids):
            feedback[item.message_id] = item
        messages = [
            message_payload(
                message,
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


class AppConfigView(APIView):
    @extend_schema(operation_id='app_config', tags=['chat'], responses=AppConfigOut)
    def get(self, request):
        settings = ChatSettings.load()
        return Response({
            'starter_questions': settings.starter_questions,
            'daily_limit': None if request.user.is_staff else settings.daily_question_limit,
            'remaining_today': quota.remaining(request.user),
        })
