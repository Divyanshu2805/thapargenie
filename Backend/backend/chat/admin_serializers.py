from access.policy import open_access_domains
from api.serializers import RejectUnknownFieldsMixin
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from chat.models import MAX_QUESTION_CHARS, ChatSettings, Feedback, SiteFeedback

# -- input ---------------------------------------------------------------------------


class StarterQuestionInput(RejectUnknownFieldsMixin, serializers.Serializer):
    category = serializers.CharField(max_length=40)
    text = serializers.CharField(max_length=200)


class SettingsSerializer(RejectUnknownFieldsMixin, serializers.ModelSerializer):
    daily_question_limit = serializers.IntegerField(min_value=1, max_value=1000)
    global_daily_llm_calls = serializers.IntegerField(min_value=100, max_value=1_000_000)
    starter_questions = StarterQuestionInput(many=True, max_length=8)
    # Set by the deployment (OPEN_ACCESS_EMAIL_DOMAINS), shown beside the approval switch.
    open_access_domains = serializers.SerializerMethodField()

    class Meta:
        model = ChatSettings
        fields = (
            'daily_question_limit', 'global_daily_llm_calls', 'rerank_enabled',
            'cache_enabled', 'contextualize_default', 'auto_title_enabled',
            'maintenance_mode', 'maintenance_message', 'banner_text', 'starter_questions',
            'require_approval', 'open_access_domains', 'updated_at',
        )
        read_only_fields = ('updated_at',)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_open_access_domains(self, obj):
        return list(open_access_domains())

    def validate_starter_questions(self, value):
        # Partial updates make nested fields optional too; each question needs both.
        if any(not item.get('category') or not item.get('text') for item in value):
            raise serializers.ValidationError('Each question needs a category and a text.')
        return value

    def validate(self, attrs):
        maintenance = attrs.get('maintenance_mode', getattr(self.instance, 'maintenance_mode',
                                                            False))
        message = attrs.get('maintenance_message',
                            getattr(self.instance, 'maintenance_message', ''))
        if maintenance and not message.strip():
            raise serializers.ValidationError(
                {'maintenance_message': ['Tell students why the service is paused.']}
            )
        return attrs

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        for name in ('maintenance_message', 'banner_text'):
            if name in values:
                values[name] = ' '.join(values[name].split())
        if 'starter_questions' in values:
            values['starter_questions'] = [dict(item) for item in values['starter_questions']]
        return values


class FeedbackReviewSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    review_status = serializers.ChoiceField(choices=Feedback.Review.choices, required=False)
    admin_note = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Nothing to change.')
        return attrs


class HistoryItemSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    role = serializers.ChoiceField(choices=('user', 'assistant'))
    content = serializers.CharField(max_length=4000)


class PlaygroundSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    query = serializers.CharField(max_length=MAX_QUESTION_CHARS)
    history = HistoryItemSerializer(many=True, required=False, max_length=8)
    rerank = serializers.BooleanField(required=False, allow_null=True, default=None)

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError('The query cannot be empty.')
        return value.strip()


# -- output (documentation only) -----------------------------------------------------


class UsageOut(serializers.Serializer):
    questions = serializers.IntegerField()
    answers = serializers.IntegerField()
    cached = serializers.IntegerField()
    llm_calls = serializers.IntegerField()
    prompt_tokens = serializers.IntegerField()
    completion_tokens = serializers.IntegerField()


class DailyUsageOut(UsageOut):
    day = serializers.DateField()


class LatencyOut(serializers.Serializer):
    p50_ms = serializers.IntegerField(allow_null=True)
    p95_ms = serializers.IntegerField(allow_null=True)
    uncached_p50_ms = serializers.IntegerField(allow_null=True)
    uncached_p95_ms = serializers.IntegerField(allow_null=True)


class FeedbackCountsOut(serializers.Serializer):
    up = serializers.IntegerField()
    down = serializers.IntegerField()
    open_reviews = serializers.IntegerField()


class BudgetOut(serializers.Serializer):
    llm_calls_today = serializers.IntegerField()
    global_daily_llm_calls = serializers.IntegerField()


class ExpiringDocumentOut(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    valid_until = serializers.DateField()


class KnowledgeOut(serializers.Serializer):
    documents_by_status = serializers.DictField(child=serializers.IntegerField())
    documents_by_category = serializers.DictField(child=serializers.IntegerField())
    chunks = serializers.IntegerField()
    searchable_chunks = serializers.IntegerField()
    cache_entries = serializers.IntegerField()
    expiring_soon = serializers.IntegerField(help_text='"Valid until" within the next 30 days.')
    expiring = ExpiringDocumentOut(many=True, help_text='The soonest, at most 5.')
    expired = serializers.IntegerField(help_text='Documents past their "valid until" date.')


class EvalRunOut(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    trigger = serializers.CharField()
    cases = serializers.IntegerField()
    recall_at_5 = serializers.FloatField()
    recall_at_10 = serializers.FloatField()
    mrr = serializers.FloatField()
    errors = serializers.IntegerField()
    misses = serializers.ListField(child=serializers.CharField())
    important_misses = serializers.ListField(child=serializers.CharField())


class QualityWarningOut(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class QualityOut(serializers.Serializer):
    latest = EvalRunOut(allow_null=True)
    previous = EvalRunOut(allow_null=True)
    warnings = QualityWarningOut(many=True)


class StatsOut(serializers.Serializer):
    range_days = serializers.IntegerField()
    totals = UsageOut()
    daily = DailyUsageOut(many=True)
    answer_types = serializers.DictField(child=serializers.IntegerField())
    cache_hit_rate = serializers.FloatField(allow_null=True)
    feedback = FeedbackCountsOut()
    latency = LatencyOut()
    budget = BudgetOut()
    knowledge = KnowledgeOut()
    database_bytes = serializers.IntegerField()
    quality = QualityOut(help_text='The nightly search-quality check.')


class FeedbackSourceOut(serializers.Serializer):
    position = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField(allow_blank=True)
    heading_path = serializers.CharField(allow_blank=True)
    cited = serializers.BooleanField()
    score = serializers.FloatField(allow_null=True)
    document_id = serializers.UUIDField(allow_null=True)
    chunk_id = serializers.UUIDField(allow_null=True)


class FeedbackAnswerOut(serializers.Serializer):
    content = serializers.CharField(allow_blank=True)
    answer_type = serializers.CharField(allow_null=True)
    grounded = serializers.BooleanField(allow_null=True)
    model = serializers.CharField(allow_blank=True)
    latency_ms = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    sources = FeedbackSourceOut(many=True)


class TraceOut(serializers.Serializer):
    standalone_query = serializers.CharField(allow_blank=True)
    analysis = serializers.JSONField()
    retrieval = serializers.JSONField()
    timings = serializers.JSONField()


class FeedbackItemOut(serializers.Serializer):
    id = serializers.UUIDField()
    rating = serializers.IntegerField()
    reason = serializers.CharField(allow_null=True)
    comment = serializers.CharField(allow_blank=True)
    review_status = serializers.ChoiceField(choices=Feedback.Review.choices)
    admin_note = serializers.CharField(allow_blank=True)
    reviewed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    reporter = serializers.CharField(help_text='Stable pseudonym; not reversible.')
    question = serializers.CharField(allow_blank=True)
    answer = FeedbackAnswerOut()
    trace = TraceOut(allow_null=True)


class SiteFeedbackItemOut(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=SiteFeedback.Kind.choices)
    rating = serializers.IntegerField(allow_null=True)
    message = serializers.CharField()
    page = serializers.CharField(allow_blank=True)
    review_status = serializers.ChoiceField(choices=SiteFeedback.Review.choices)
    admin_note = serializers.CharField(allow_blank=True)
    reviewed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    reporter = serializers.CharField(help_text='Stable pseudonym; not reversible.')
    contact_email = serializers.EmailField(
        allow_null=True, help_text='Only when the student agreed to be contacted.'
    )


class GapOut(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()
    askers = serializers.IntegerField()
    last_seen = serializers.DateTimeField()


class GapsOut(serializers.Serializer):
    range_days = serializers.IntegerField()
    results = GapOut(many=True)


class ComplaintOut(serializers.Serializer):
    remark = serializers.CharField(help_text='What the student said about the earlier answer.')
    question = serializers.CharField(help_text='The question that earlier answer was for.')
    answer = serializers.CharField(help_text='The start of that earlier answer.')
    created_at = serializers.DateTimeField()
    reporter = serializers.CharField(help_text='A stable pseudonym, never the email.')


class ComplaintsOut(serializers.Serializer):
    range_days = serializers.IntegerField()
    results = ComplaintOut(many=True)


class PlaygroundSourceOut(serializers.Serializer):
    position = serializers.IntegerField()
    title = serializers.CharField()
    url = serializers.CharField(allow_blank=True)
    heading_path = serializers.CharField(allow_blank=True)
    page_start = serializers.IntegerField(allow_null=True)
    page_end = serializers.IntegerField(allow_null=True)
    academic_year = serializers.CharField(allow_blank=True)
    category = serializers.CharField(allow_blank=True)
    snippet = serializers.CharField(allow_blank=True)
    document_id = serializers.UUIDField()
    chunk_ids = serializers.ListField(child=serializers.UUIDField())
    score = serializers.FloatField()
    is_current = serializers.BooleanField()
    content = serializers.CharField()
    cited = serializers.BooleanField()


class PlaygroundUsageOut(serializers.Serializer):
    llm_calls = serializers.IntegerField()
    prompt_tokens = serializers.IntegerField()
    completion_tokens = serializers.IntegerField()


class PlaygroundOut(serializers.Serializer):
    analysis = serializers.JSONField()
    stages = serializers.ListField(child=serializers.JSONField())
    retrieval = serializers.JSONField(help_text='Per-candidate ranks, fused score, boost and '
                                                'rerank score.')
    reranked = serializers.BooleanField()
    sources = PlaygroundSourceOut(many=True)
    answer = serializers.CharField(allow_blank=True)
    answer_type = serializers.CharField()
    grounded = serializers.BooleanField(allow_null=True)
    unsupported = serializers.ListField(child=serializers.CharField())
    model = serializers.CharField(allow_blank=True)
    timings = serializers.DictField(child=serializers.IntegerField())
    usage = PlaygroundUsageOut()
