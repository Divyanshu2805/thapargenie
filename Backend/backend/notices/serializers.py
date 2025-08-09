from api.serializers import RejectUnknownFieldsMixin
from django.utils import timezone
from knowledge.models import Category
from rest_framework import serializers

from notices.models import MAX_BODY_CHARS, MAX_TITLE_CHARS, Notice


class NoticeWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Create (all defaults apply) or, with `partial=True` and `instance`, edit."""

    title = serializers.CharField(max_length=MAX_TITLE_CHARS)
    body = serializers.CharField(max_length=MAX_BODY_CHARS, allow_blank=True, default='')
    category = serializers.ChoiceField(choices=Category.choices, default=Category.NOTICES)
    importance = serializers.ChoiceField(choices=Notice.Importance.choices,
                                         default=Notice.Importance.NORMAL)
    is_pinned = serializers.BooleanField(default=False)
    is_draft = serializers.BooleanField(default=False)
    publish_at = serializers.DateTimeField(
        required=False, allow_null=True, help_text='Empty or null: now. A future time schedules it.'
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    link_url = serializers.URLField(max_length=2000, allow_blank=True, default='')
    answerable = serializers.BooleanField(
        default=True, help_text='Also add it to the knowledge base while it is published.'
    )

    def validate_link_url(self, value):
        if value and not value.startswith('https://'):
            raise serializers.ValidationError('Only https links are allowed.')
        return value

    def validate_expires_at(self, value):
        unchanged = self.instance is not None and value == self.instance.expires_at
        if value is not None and not unchanged and value <= timezone.now():
            raise serializers.ValidationError('The expiry must be in the future.')
        return value

    def validate(self, attrs):
        instance = self.instance
        publish_at = attrs.get('publish_at', instance.publish_at if instance else None)
        publish_at = publish_at or timezone.now()
        expires_at = attrs.get('expires_at', instance.expires_at if instance else None)
        if 'expires_at' not in attrs and 'publish_at' not in attrs:
            return attrs
        if expires_at is not None and expires_at <= publish_at:
            raise serializers.ValidationError(
                {'expires_at': ['The expiry must be after the publish time.']})
        return attrs


def notice_payload(notice):
    """What students see."""
    return {
        'id': str(notice.pk),
        'title': notice.title,
        'body': notice.body,
        'category': notice.category,
        'importance': notice.importance,
        'is_pinned': notice.is_pinned,
        'publish_at': notice.publish_at,
        'expires_at': notice.expires_at,
        'link_url': notice.link_url,
        'updated_at': notice.updated_at,
    }


def admin_notice_payload(notice, now=None):
    document = notice.document
    return {
        **notice_payload(notice),
        'is_draft': notice.is_draft,
        'answerable': notice.answerable,
        'state': notice.state(now),
        'document': None if document is None else {
            'id': str(document.pk), 'status': document.status,
            'is_current': document.is_current,
        },
        'created_by': notice.created_by.email if notice.created_by else None,
        'updated_by': notice.updated_by.email if notice.updated_by else None,
        'created_at': notice.created_at,
    }


def official_payload(document):
    return {
        'id': str(document.pk),
        'title': document.title,
        'processed_at': document.processed_at,
        'effective_date': document.effective_date,
        'source_url': document.source_url,
    }


# -- response shapes, for the OpenAPI schema only ----------------------------------------

class NoticeOut(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    body = serializers.CharField(allow_blank=True)
    category = serializers.ChoiceField(choices=Category.choices)
    importance = serializers.ChoiceField(choices=Notice.Importance.choices)
    is_pinned = serializers.BooleanField()
    publish_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    link_url = serializers.CharField(allow_blank=True)
    updated_at = serializers.DateTimeField()


class NoticeListOut(serializers.Serializer):
    results = NoticeOut(many=True)


class NoticeDocumentOut(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    is_current = serializers.BooleanField()


class AdminNoticeOut(NoticeOut):
    is_draft = serializers.BooleanField()
    answerable = serializers.BooleanField()
    state = serializers.ChoiceField(choices=Notice.State.choices)
    document = NoticeDocumentOut(allow_null=True)
    created_by = serializers.EmailField(allow_null=True)
    updated_by = serializers.EmailField(allow_null=True)
    created_at = serializers.DateTimeField()


class OfficialNoticeOut(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    processed_at = serializers.DateTimeField()
    effective_date = serializers.DateField(allow_null=True)
    source_url = serializers.CharField(allow_blank=True)


class OfficialNoticeListOut(serializers.Serializer):
    results = OfficialNoticeOut(many=True)
