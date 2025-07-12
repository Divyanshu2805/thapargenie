from api.serializers import RejectUnknownFieldsMixin
from rest_framework import serializers

from knowledge.models import Category, Document, Parser

ACADEMIC_YEAR = r'^\d{4}-\d{2}$'
MAX_TEXT_CHARS = 100_000


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = (
            'id', 'title', 'source_type', 'source_url', 'original_filename', 'mime_type',
            'file_size', 'page_count', 'category', 'department', 'academic_year',
            'effective_date', 'is_current', 'status', 'status_detail', 'error',
            'parser', 'chunk_count', 'token_count', 'embedding_model',
            'created_at', 'updated_at', 'processed_at',
        )
        read_only_fields = fields


class DocumentMetaSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Metadata accepted when adding a document. Defaults come from the model."""

    category = serializers.ChoiceField(choices=Category.choices, required=False)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)
    academic_year = serializers.RegexField(ACADEMIC_YEAR, required=False, allow_blank=True)
    effective_date = serializers.DateField(required=False, allow_null=True)
    is_current = serializers.BooleanField(required=False)
    source_url = serializers.URLField(max_length=2000, required=False, allow_blank=True)
    parser = serializers.ChoiceField(choices=Parser.choices, required=False)

    def validate_source_url(self, value):
        if value and not value.startswith('https://'):
            raise serializers.ValidationError('Only https links are allowed.')
        return value


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


class ReprocessSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    parser = serializers.ChoiceField(choices=Parser.choices, required=False)


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
