from api.serializers import RejectUnknownFieldsMixin
from rest_framework import serializers

from knowledge.models import MAX_CHUNK_CHARS, Category, Chunk, Document, Parser

ACADEMIC_YEAR = r'^\d{4}-\d{2}$'
MAX_TEXT_CHARS = 100_000


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            'id', 'title', 'source_type', 'source_url', 'original_filename', 'mime_type',
            'file_size', 'page_count', 'category', 'department', 'academic_year',
            'effective_date', 'valid_until', 'is_current', 'status', 'status_detail', 'error',
            'parser', 'contextualize', 'chunk_count', 'token_count', 'embedding_model',
            'created_at', 'updated_at', 'processed_at',
        )
        read_only_fields = fields


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = (
            'id', 'chunk_index', 'content', 'heading_path', 'page_start', 'page_end',
            'token_count', 'is_searchable', 'embedding_model', 'updated_at',
        )
        read_only_fields = fields


class DocumentMetaSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Metadata accepted when adding a document. Defaults come from the model."""

    category = serializers.ChoiceField(choices=Category.choices, required=False)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)
    academic_year = serializers.RegexField(ACADEMIC_YEAR, required=False, allow_blank=True)
    effective_date = serializers.DateField(required=False, allow_null=True)
    valid_until = serializers.DateField(
        required=False, allow_null=True,
        help_text='Last day the document applies; after it, it is marked not current.',
    )
    is_current = serializers.BooleanField(required=False)
    source_url = serializers.URLField(max_length=2000, required=False, allow_blank=True)
    parser = serializers.ChoiceField(choices=Parser.choices, required=False)
    contextualize = serializers.BooleanField(required=False)

    def validate_source_url(self, value):
        if value and not value.startswith('https://'):
            raise serializers.ValidationError('Only https links are allowed.')
        return value

    def validate(self, attrs):
        start, end = attrs.get('effective_date'), attrs.get('valid_until')
        if start and end and end < start:
            raise serializers.ValidationError(
                {'valid_until': ['"Valid until" cannot be before the effective date.']})
        return attrs


class UploadSerializer(DocumentMetaSerializer):
    # A single file may set its own title; several files take their file names.
    title = serializers.CharField(max_length=300, required=False)


class UploadSchema(UploadSerializer):
    """Documentation only: the multipart body, including the files."""

    files = serializers.ListField(child=serializers.FileField(), max_length=10)


class UrlDocumentSerializer(DocumentMetaSerializer):
    url = serializers.URLField(max_length=2000)
    title = serializers.CharField(max_length=300, required=False)
    source_url = None


class TextDocumentSerializer(DocumentMetaSerializer):
    title = serializers.CharField(max_length=300)
    text = serializers.CharField(max_length=MAX_TEXT_CHARS)
    parser = None


class DocumentUpdateSerializer(DocumentMetaSerializer):
    title = serializers.CharField(max_length=300, required=False)
    parser = None


MAX_BULK_IDS = 100
BULK_ACTIONS = ('update', 'enable', 'disable', 'reprocess', 'delete')


class BulkChangesSerializer(DocumentMetaSerializer):
    """Fields that make sense to set on many documents at once."""

    source_url = None
    parser = None
    contextualize = None


class BulkActionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    action = serializers.ChoiceField(choices=BULK_ACTIONS)
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1,
                                max_length=MAX_BULK_IDS)
    changes = BulkChangesSerializer(required=False)
    # Per-document values for "update" (e.g. reviewed suggestions), keyed by document id.
    changes_by_id = serializers.DictField(child=BulkChangesSerializer(), required=False)

    def validate(self, attrs):
        # Keep the caller's order, drop repeats.
        attrs['ids'] = list(dict.fromkeys(attrs['ids']))
        shared, per_document = attrs.get('changes'), attrs.get('changes_by_id')
        if attrs['action'] != 'update':
            if 'changes' in attrs or 'changes_by_id' in attrs:
                raise serializers.ValidationError(
                    {'changes': ['Only the "update" action takes changes.']})
            return attrs
        if (shared is None) == (per_document is None):
            raise serializers.ValidationError(
                {'changes': ['Send either "changes" or "changes_by_id".']})
        if shared is not None and not shared:
            raise serializers.ValidationError({'changes': ['Choose at least one field.']})
        if per_document is not None:
            if set(per_document) != {str(document_id) for document_id in attrs['ids']}:
                raise serializers.ValidationError(
                    {'changes_by_id': ['Give changes for exactly the documents in "ids".']})
            if not all(per_document.values()):
                raise serializers.ValidationError(
                    {'changes_by_id': ['Each document needs at least one field.']})
        return attrs


class MatchingIdsSerializer(serializers.Serializer):
    count = serializers.IntegerField(help_text='All documents matching the filters.')
    ids = serializers.ListField(child=serializers.UUIDField(), help_text='Newest first, ≤ 2,000.')
    truncated = serializers.BooleanField()


class BulkFailureSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    message = serializers.CharField()


class BulkResultSerializer(serializers.Serializer):
    succeeded = serializers.ListField(child=serializers.UUIDField())
    failed = BulkFailureSerializer(many=True)


class ReprocessSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    parser = serializers.ChoiceField(choices=Parser.choices, required=False)


class ChunkUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    content = serializers.CharField(max_length=MAX_CHUNK_CHARS, required=False)
    heading_path = serializers.CharField(max_length=500, required=False, allow_blank=True)


class UploadResultSerializer(serializers.Serializer):
    class Rejected(serializers.Serializer):
        filename = serializers.CharField()
        code = serializers.CharField()
        message = serializers.CharField()
        existing_id = serializers.UUIDField(required=False)

    created = DocumentSerializer(many=True)
    rejected = Rejected(many=True)


class FileUrlSerializer(serializers.Serializer):
    url = serializers.URLField()
