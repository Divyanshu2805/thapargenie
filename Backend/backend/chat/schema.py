"""Response shapes for the OpenAPI schema (documentation only, never used to validate)."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers

from chat.models import Feedback, Message
from chat.serializers import ConversationSerializer


class SourceOut(serializers.Serializer):
    position = serializers.IntegerField()
    source_id = serializers.UUIDField()
    title = serializers.CharField()
    url = serializers.CharField(allow_blank=True)
    heading_path = serializers.CharField(allow_blank=True)
    page_start = serializers.IntegerField(allow_null=True)
    page_end = serializers.IntegerField(allow_null=True)
    academic_year = serializers.CharField(allow_blank=True)
    effective_date = serializers.DateField(allow_null=True)
    is_current = serializers.BooleanField(allow_null=True,
                                          help_text='Null if the document was deleted.')
    category = serializers.CharField(allow_blank=True)
    snippet = serializers.CharField(allow_blank=True)
    cited = serializers.BooleanField()


class SearchMatchOut(serializers.Serializer):
    role = serializers.ChoiceField(choices=Message.Role.choices)
    snippet = serializers.CharField()


class ConversationListOut(ConversationSerializer):
    match = SearchMatchOut(allow_null=True, required=False, help_text=(
        'Only when searching: the newest message containing the words, or null when only '
        'the title matched.'))

    class Meta(ConversationSerializer.Meta):
        fields = (*ConversationSerializer.Meta.fields, 'match')


class FeedbackOut(serializers.Serializer):
    rating = serializers.ChoiceField(choices=(-1, 1))
    reason = serializers.ChoiceField(choices=Feedback.Reason.choices, allow_null=True)
    comment = serializers.CharField(allow_blank=True)


class SiblingsOut(serializers.Serializer):
    index = serializers.IntegerField()
    count = serializers.IntegerField()
    ids = serializers.ListField(child=serializers.UUIDField())


class MessageOut(serializers.Serializer):
    id = serializers.UUIDField()
    parent_id = serializers.UUIDField(allow_null=True)
    role = serializers.ChoiceField(choices=Message.Role.choices)
    content = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=Message.Status.choices)
    answer_type = serializers.ChoiceField(choices=Message.AnswerType.choices, allow_null=True)
    grounded = serializers.BooleanField(allow_null=True)
    error_code = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    sources = SourceOut(many=True)
    feedback = FeedbackOut(allow_null=True)
    siblings = SiblingsOut(required=False)


class MessagesOut(serializers.Serializer):
    conversation = ConversationSerializer()
    messages = MessageOut(many=True)


class StarterQuestion(serializers.Serializer):
    category = serializers.CharField()
    text = serializers.CharField()


class AppConfigOut(serializers.Serializer):
    banner = serializers.CharField(allow_null=True)
    maintenance = serializers.BooleanField()
    maintenance_message = serializers.CharField(allow_null=True)
    starter_questions = StarterQuestion(many=True)
    daily_limit = serializers.IntegerField(allow_null=True)
    remaining_today = serializers.IntegerField(allow_null=True)


class UrlOut(serializers.Serializer):
    url = serializers.URLField()


EVENT_STREAM = OpenApiResponse(
    response=OpenApiTypes.STR,
    description=(
        'text/event-stream. Events, in order: `meta` {conversation_id, user_message_id, '
        'assistant_message_id, regenerated, remaining_today}; zero or more `status` '
        '{stage: understanding|searching|reading|writing, detail?}; `sources` {sources[]}; '
        '`delta` {text} (repeated); then `done` {message, remaining_today} or `error` '
        '{code, message, retryable}. `: ping` comments keep the connection open.'
    ),
)
