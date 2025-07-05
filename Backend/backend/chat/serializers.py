from api.serializers import RejectUnknownFieldsMixin
from rest_framework import serializers

from chat.models import (
    MAX_QUESTION_CHARS,
    Conversation,
    Feedback,
    Message,
)


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = (
            'id', 'title', 'is_pinned', 'is_archived', 'message_count', 'last_message_at',
            'created_at',
        )
        read_only_fields = fields


def search_snippet(content, query, width=60):
    """Plain text around the first case-insensitive match of `query` in `content`."""
    text = ' '.join(content.split())
    at = text.lower().find(query.lower())
    if at < 0:
        return text[: width * 2] + ('…' if len(text) > width * 2 else '')
    start, end = max(0, at - width), min(len(text), at + len(query) + width)
    return ('…' if start else '') + text[start:end] + ('…' if end < len(text) else '')


class ConversationCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)


class ConversationUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    title = serializers.CharField(max_length=120, required=False, allow_blank=False)
    is_pinned = serializers.BooleanField(required=False)
    is_archived = serializers.BooleanField(required=False)
    current_leaf_id = serializers.UUIDField(required=False)

    def validate_title(self, value):
        value = ' '.join(value.split())
        if not value:
            raise serializers.ValidationError('Title cannot be empty.')
        return value


class AskSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    content = serializers.CharField(max_length=MAX_QUESTION_CHARS, trim_whitespace=True)
    client_request_id = serializers.UUIDField()
    edit_of = serializers.UUIDField(required=False)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('Question cannot be empty.')
        return value


class RegenerateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    client_request_id = serializers.UUIDField()


class FeedbackSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    rating = serializers.ChoiceField(choices=(-1, 1))
    reason = serializers.ChoiceField(choices=Feedback.Reason.choices, required=False,
                                     allow_null=True)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)


def source_payload(source):
    """A cited source. The current flag is read live from the document, so an answer
    shows a later "replaced" warning too; load `document` with select_related."""
    document = source.document
    return {
        'position': source.position,
        'source_id': str(source.pk),
        'title': source.title,
        'url': source.url,
        'heading_path': source.heading_path,
        'page_start': source.page_start,
        'page_end': source.page_end,
        'academic_year': source.academic_year,
        'is_current': document.is_current if document else None,
        'category': source.category,
        'snippet': source.snippet,
        'cited': source.cited,
    }


def feedback_payload(feedback):
    if feedback is None:
        return None
    return {'rating': feedback.rating, 'reason': feedback.reason, 'comment': feedback.comment}


def message_payload(message, *, siblings=None, sources=None, feedback=None):
    """Public JSON for one message. Pass prefetched relations to avoid extra queries."""
    if sources is None:
        sources = (
            list(message.sources.select_related('document'))
            if message.role == Message.Role.ASSISTANT else []
        )
    if feedback is None and message.role == Message.Role.ASSISTANT:
        feedback = Feedback.objects.filter(message=message).first()
    payload = {
        'id': str(message.pk),
        'parent_id': str(message.parent_id) if message.parent_id else None,
        'role': message.role,
        'content': message.content,
        'status': message.status,
        'answer_type': message.answer_type,
        'grounded': message.grounded,
        'error_code': message.error_code or None,
        'created_at': message.created_at.isoformat(),
        'sources': [source_payload(source) for source in sources],
        'feedback': feedback_payload(feedback),
    }
    if siblings is not None:
        payload['siblings'] = siblings
    return payload
