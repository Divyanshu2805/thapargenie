from api.serializers import RejectUnknownFieldsMixin
from rest_framework import serializers

from chat.models import ChatSettings, Feedback

# -- input ---------------------------------------------------------------------------


class StarterQuestionInput(RejectUnknownFieldsMixin, serializers.Serializer):
    category = serializers.CharField(max_length=40)
    text = serializers.CharField(max_length=200)


class SettingsSerializer(RejectUnknownFieldsMixin, serializers.ModelSerializer):
    daily_question_limit = serializers.IntegerField(min_value=1, max_value=1000)
    global_daily_llm_calls = serializers.IntegerField(min_value=100, max_value=1_000_000)
    starter_questions = StarterQuestionInput(many=True, max_length=8)

    class Meta:
        model = ChatSettings
        fields = (
            'daily_question_limit', 'global_daily_llm_calls', 'rerank_enabled',
            'cache_enabled', 'contextualize_default', 'auto_title_enabled',
            'maintenance_mode', 'maintenance_message', 'banner_text', 'starter_questions',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

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


class KnowledgeOut(serializers.Serializer):
    documents_by_status = serializers.DictField(child=serializers.IntegerField())
    documents_by_category = serializers.DictField(child=serializers.IntegerField())
    chunks = serializers.IntegerField()
    searchable_chunks = serializers.IntegerField()
    cache_entries = serializers.IntegerField()


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


class GapOut(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()
    askers = serializers.IntegerField()
    last_seen = serializers.DateTimeField()


class GapsOut(serializers.Serializer):
    range_days = serializers.IntegerField()
    results = GapOut(many=True)
