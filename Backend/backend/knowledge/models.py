from common.mixins import TimestampedModel, UUIDModel, choices_check, max_length_check
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from pgvector.django import HalfVectorField, HnswIndex

EMBED_DIMENSIONS = 768
MAX_CHUNK_CHARS = 12_000


class Category(models.TextChoices):
    ADMISSIONS = 'admissions', 'Admissions'
    FEES_SCHOLARSHIPS = 'fees_scholarships', 'Fees & scholarships'
    HOSTEL_CAMPUS_LIFE = 'hostel_campus_life', 'Hostels & campus life'
    ACADEMIC_CALENDAR = 'academic_calendar', 'Academic calendar'
    COURSES_SYLLABUS = 'courses_syllabus', 'Courses & syllabus'
    RULES_REGULATIONS = 'rules_regulations', 'Rules & regulations'
    DEPARTMENTS = 'departments', 'Departments'
    FACULTY = 'faculty', 'Faculty'
    PLACEMENTS = 'placements', 'Placements'
    NOTICES = 'notices', 'Notices'
    ABOUT_CONTACT = 'about_contact', 'About & contact'
    FAQ = 'faq', 'FAQ'
    OTHER = 'other', 'Other'


class SourceType(models.TextChoices):
    PDF = 'pdf', 'PDF'
    DOCX = 'docx', 'Word'
    URL = 'url', 'Web page'
    TEXT = 'text', 'Text / FAQ'
    CRAWLER = 'crawler', 'Crawler import'


class DocumentStatus(models.TextChoices):
    QUEUED = 'queued', 'Queued'
    PROCESSING = 'processing', 'Processing'
    READY = 'ready', 'Ready'
    FAILED = 'failed', 'Failed'
    DISABLED = 'disabled', 'Disabled'


class Document(UUIDModel, TimestampedModel):
    title = models.CharField(max_length=300)
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    source_url = models.URLField(max_length=2000, blank=True)
    storage_path = models.CharField(max_length=300, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, unique=True)

    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)
    department = models.CharField(max_length=120, blank=True)
    academic_year = models.CharField(max_length=7, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)

    status = models.CharField(
        max_length=16, choices=DocumentStatus.choices, default=DocumentStatus.QUEUED
    )
    status_detail = models.CharField(max_length=200, blank=True)
    error = models.CharField(max_length=500, blank=True)

    chunk_count = models.PositiveIntegerField(default=0)
    token_count = models.PositiveIntegerField(default=0)
    embedding_model = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('status',), name='document_status_idx'),
            models.Index(fields=('category', 'is_current'), name='document_category_idx'),
            models.Index(fields=('-created_at',), name='document_created_idx'),
            GinIndex(fields=('title',), opclasses=('gin_trgm_ops',), name='document_title_trgm'),
        ]
        constraints = [
            choices_check('source_type', SourceType, 'document_source_type_valid'),
            choices_check('category', Category, 'document_category_valid'),
            choices_check('status', DocumentStatus, 'document_status_valid'),
            models.CheckConstraint(
                condition=models.Q(academic_year='')
                | models.Q(academic_year__regex=r'^\d{4}-\d{2}$'),
                name='document_academic_year_format',
            ),
            models.CheckConstraint(
                condition=models.Q(source_url='') | models.Q(source_url__startswith='https://'),
                name='document_source_url_https',
            ),
        ]

    def __str__(self):
        return self.title


class Chunk(UUIDModel, TimestampedModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    search_text = models.TextField()
    heading_path = models.CharField(max_length=500, blank=True)
    page_start = models.PositiveIntegerField(null=True, blank=True)
    page_end = models.PositiveIntegerField(null=True, blank=True)
    token_count = models.PositiveIntegerField(default=0)

    embedding = HalfVectorField(dimensions=EMBED_DIMENSIONS, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True)

    # Copied from the document so retrieval can filter without a join.
    category = models.CharField(max_length=32, choices=Category.choices)
    department = models.CharField(max_length=120, blank=True)
    is_current = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=False)

    fts = models.GeneratedField(
        expression=SearchVector('heading_path', weight='A', config='english')
        + SearchVector('search_text', weight='B', config='english'),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        ordering = ('document', 'chunk_index')
        indexes = [
            HnswIndex(
                fields=('embedding',),
                name='chunk_embedding_hnsw',
                m=16,
                ef_construction=64,
                opclasses=('halfvec_cosine_ops',),
                condition=models.Q(is_searchable=True),
            ),
            GinIndex(fields=('fts',), name='chunk_fts_gin'),
            models.Index(fields=('category', 'is_current'), name='chunk_category_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=('document', 'chunk_index'), name='chunk_unique_index'),
            choices_check('category', Category, 'chunk_category_valid'),
            max_length_check('content', MAX_CHUNK_CHARS, 'chunk_content_length'),
            models.CheckConstraint(
                condition=models.Q(page_start__isnull=True)
                | models.Q(page_end__isnull=True)
                | models.Q(page_end__gte=models.F('page_start')),
                name='chunk_page_range_valid',
            ),
        ]

    def __str__(self):
        return f'{self.document_id}#{self.chunk_index}'
