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
    SharedViewThrottle,
    SiteFeedbackThrottle,
    SuggestThrottle,
)
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from knowledge.storage import StorageError, get_storage
from notices.services import app_config_fields as notice_fields
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from chat import answering, cache, coverage, engine, quota, sharing, suggestions
from chat.models import (
    ChatSettings,
    Conversation,
    Feedback,
    Message,
    MessageSource,
    SiteFeedback,
)
from chat.schema import (
    EVENT_STREAM,
    AppConfigOut,
    ConversationListOut,
    CoverageOut,
    FeedbackOut,
    MessagesOut,
    SharedAnswerOut,
    ShareOut,
    ShareStateOut,
    SiteFeedbackListOut,
    SiteFeedbackOut,
    SuggestionsOut,
    UrlOut,
)
from chat.serializers import (
    AskSerializer,
    ConversationCreateSerializer,
    ConversationSerializer,
    ConversationUpdateSerializer,
    FeedbackSerializer,
    RegenerateSerializer,
    SiteFeedbackSerializer,
    feedback_payload,
    message_payload,
    search_snippet,
    shown_sources,
    site_feedback_payload,
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
        edit_of = None
        if 'edit_of' in data:
            edit_of = get_object_or_404(
                Message, pk=data['edit_of'], conversation=conversation
            )
        turn = answering.start_turn(
            request.user,
            conversation,
            content=data['content'],
            client_request_id=data['client_request_id'],
            edit_of=edit_of,
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


class SuggestionsView(APIView):
    """Follow-up questions for one answer, generated on request and then kept."""

    throttle_classes = [SuggestThrottle]

    @extend_schema(operation_id='messages_suggestions', tags=['chat'], request=None,
                   responses=SuggestionsOut)
    def post(self, request, message_id):
        message = owned_message(request, message_id)
        return Response({'suggestions': suggestions.suggest(message, request.user)})


def share_payload(shared):
    return {'token': shared.token, 'created_at': shared.created_at,
            'expires_at': shared.expires_at}


class ShareView(APIView):
    """The student's 7-day public link to one answer."""

    @extend_schema(operation_id='messages_share_retrieve', tags=['chat'], responses=ShareStateOut)
    def get(self, request, message_id):
        message = owned_message(request, message_id)
        shared = sharing.active_share(message, request.user)
        return Response({'share': share_payload(shared) if shared else None})

    @extend_schema(operation_id='messages_share_create', tags=['chat'], request=None,
                   responses={200: ShareOut, 201: ShareOut})
    def post(self, request, message_id):
        message = owned_message(request, message_id)
        try:
            shared, created = sharing.share(message, request.user, request_id=request_id(request))
        except sharing.NotShareable as exc:
            return error_response(request, status.HTTP_409_CONFLICT, 'not_shareable', str(exc))
        return Response(share_payload(shared),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(operation_id='messages_share_revoke', tags=['chat'], responses={204: None})
    def delete(self, request, message_id):
        message = owned_message(request, message_id)
        sharing.revoke(message, request.user, request_id=request_id(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SharedAnswerView(APIView):
    """Public: anyone with the link, no sign-in and no token read at all."""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [SharedViewThrottle]

    @extend_schema(operation_id='shared_answer', tags=['chat'], auth=[],
                   responses=SharedAnswerOut)
    def get(self, request, token):
        shared = sharing.public(token)
        if shared is None:
            raise Http404
        response = Response({
            'question': shared.question,
            'answer': shared.answer,
            'sources': shared.sources,
            'created_at': shared.created_at,
            'expires_at': shared.expires_at,
        })
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Cache-Control'] = 'no-store'
        return response


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
                'review_status': Feedback.Review.OPEN,
            },
        )
        if data['rating'] < 0:
            cache.forget_answer(message.content)
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
            'banner': settings.banner_text or None,
            'maintenance': settings.maintenance_mode,
            'maintenance_message': settings.maintenance_message or None,
            'starter_questions': settings.starter_questions,
            'daily_limit': None if request.user.is_staff else settings.daily_question_limit,
            'remaining_today': quota.remaining(request.user),
            **notice_fields(),
        })


class CoverageView(APIView):
    """Topics the knowledge base covers, with document counts."""

    @extend_schema(operation_id='coverage', tags=['chat'], responses=CoverageOut)
    def get(self, request):
        return Response(coverage.summary())


class SiteFeedbackView(APIView):
    """Feedback and suggestions about the site itself."""

    HISTORY = 20

    def get_throttles(self):
        throttles = super().get_throttles()
        return [*throttles, SiteFeedbackThrottle()] if self.request.method == 'POST' else throttles

    @extend_schema(operation_id='site_feedback_list', tags=['chat'], responses=SiteFeedbackListOut)
    def get(self, request):
        items = SiteFeedback.objects.filter(user=request.user).order_by('-created_at')
        items = items[:self.HISTORY]
        return Response({'results': [site_feedback_payload(item) for item in items]})

    @extend_schema(operation_id='site_feedback_create', tags=['chat'],
                   request=SiteFeedbackSerializer, responses={201: SiteFeedbackOut})
    def post(self, request):
        serializer = SiteFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = SiteFeedback.objects.create(
            user=request.user,
            kind=data['kind'],
            rating=data.get('rating'),
            message=data['message'],
            page=data.get('page', ''),
            contact_ok=data['contact_ok'],
        )
        return Response(site_feedback_payload(item), status=status.HTTP_201_CREATED)


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
                            'sources': [source_payload(s) for s in
                                        shown_sources(message, message.sources.all())],
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
        response['Content-Disposition'] = 'attachment; filename="thapargenie-export.json"'
        audit(request.user, 'privacy.exported', 'user', request.user.pk,
              request_id=request_id(request), conversations=len(data['conversations']))
        return response
