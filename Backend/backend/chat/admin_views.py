"""Admin API for chat insight and control. No conversation browsing."""

from common.admin_api import AdminAPIView, choice_param, paginate, request_id
from common.audit import audit
from common.csv_export import csv_response
from common.throttles import AdminExportThrottle
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from knowledge.errors import LLMUnavailable
from rag.llm import LLMError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from chat import admin_services
from chat.admin_serializers import (
    ComplaintsOut,
    FeedbackItemOut,
    FeedbackReviewSerializer,
    GapsOut,
    PlaygroundOut,
    PlaygroundSerializer,
    SettingsSerializer,
    SiteFeedbackItemOut,
    StatsOut,
)
from chat.models import ChatSettings, Feedback, Message, SiteFeedback

TAGS = ['admin: chat']
RANGE_PARAM = OpenApiParameter('range', str, enum=list(admin_services.RANGES), default='7d')


def _range(request, default):
    value = request.query_params.get('range', default)
    if value not in admin_services.RANGES:
        raise ValidationError({'range': [f'Use one of: {", ".join(admin_services.RANGES)}.']})
    return admin_services.RANGES[value]


class StatsView(AdminAPIView):
    @extend_schema(operation_id='admin_stats', tags=TAGS, parameters=[RANGE_PARAM],
                   responses=StatsOut)
    def get(self, request):
        return Response(admin_services.stats(_range(request, '7d')))


class GapsView(AdminAPIView):
    @extend_schema(operation_id='admin_gaps', tags=TAGS,
                   parameters=[OpenApiParameter('range', str, enum=list(admin_services.RANGES),
                                                default='30d')],
                   responses=GapsOut)
    def get(self, request):
        days = _range(request, '30d')
        return Response({'range_days': days, 'results': admin_services.gaps(days)})


class ComplaintsView(AdminAPIView):
    @extend_schema(operation_id='admin_complaints', tags=TAGS,
                   parameters=[OpenApiParameter('range', str, enum=list(admin_services.RANGES),
                                                default='30d')],
                   responses=ComplaintsOut)
    def get(self, request):
        days = _range(request, '30d')
        return Response({'range_days': days, 'results': admin_services.complaints(days)})


class FeedbackListView(AdminAPIView):
    @extend_schema(
        operation_id='admin_feedback_list',
        tags=TAGS,
        parameters=[
            OpenApiParameter('review_status', str, enum=Feedback.Review.values),
            OpenApiParameter('rating', int, enum=[-1, 1]),
            OpenApiParameter('answer_type', str, enum=Message.AnswerType.values),
            OpenApiParameter('reason', str, enum=Feedback.Reason.values),
        ],
        responses=FeedbackItemOut(many=True),
    )
    def get(self, request):
        rating = choice_param(request, 'rating', ('1', '-1'))
        items = admin_services.feedback_queryset(
            review_status=choice_param(request, 'review_status', Feedback.Review.values),
            rating=int(rating) if rating else None,
            answer_type=choice_param(request, 'answer_type', Message.AnswerType.values),
            reason=choice_param(request, 'reason', Feedback.Reason.values),
        )
        return paginate(self, items, admin_services.feedback_payload)


class FeedbackDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_feedback_review', tags=TAGS,
                   request=FeedbackReviewSerializer, responses=FeedbackItemOut)
    def patch(self, request, feedback_id):
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        serializer = FeedbackReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_services.review_feedback(feedback, serializer.validated_data, user=request.user,
                                       request_id=request_id(request))
        item = admin_services.feedback_queryset().get(pk=feedback.pk)
        return Response(admin_services.feedback_payload(item))


class CsvExportView(AdminAPIView):
    """A CSV download, audited with its kind and row count."""

    kind = ''

    def get_throttles(self):
        return [*super().get_throttles(), AdminExportThrottle()]

    def send(self, request, header, rows, **metadata):
        filename = f'thapargenie-{self.kind}-{timezone.localdate().isoformat()}.csv'
        response = csv_response(filename, header, rows)
        audit(request.user, 'export.csv', 'export', self.kind, request_id=request_id(request),
              rows=response.rows_written, **metadata)
        return response


CSV_RESPONSE = {(200, 'text/csv'): {'type': 'string'}}


class FeedbackExportView(CsvExportView):
    kind = 'feedback'

    @extend_schema(
        operation_id='admin_feedback_export',
        tags=TAGS,
        parameters=[
            OpenApiParameter('review_status', str, enum=Feedback.Review.values),
            OpenApiParameter('rating', int, enum=[-1, 1]),
            OpenApiParameter('answer_type', str, enum=Message.AnswerType.values),
            OpenApiParameter('reason', str, enum=Feedback.Reason.values),
        ],
        responses=CSV_RESPONSE,
    )
    def get(self, request):
        filters = {
            'review_status': choice_param(request, 'review_status', Feedback.Review.values),
            'rating': choice_param(request, 'rating', ('1', '-1')),
            'answer_type': choice_param(request, 'answer_type', Message.AnswerType.values),
            'reason': choice_param(request, 'reason', Feedback.Reason.values),
        }
        items = admin_services.feedback_queryset(**filters)
        return self.send(request, admin_services.FEEDBACK_CSV_HEADER,
                         admin_services.feedback_csv_rows(items),
                         filters={key: value for key, value in filters.items() if value})


class GapsExportView(CsvExportView):
    kind = 'gaps'

    @extend_schema(operation_id='admin_gaps_export', tags=TAGS,
                   parameters=[OpenApiParameter('range', str, enum=list(admin_services.RANGES),
                                                default='30d')],
                   responses=CSV_RESPONSE)
    def get(self, request):
        days = _range(request, '30d')
        return self.send(request, admin_services.GAPS_CSV_HEADER,
                         admin_services.gaps_csv_rows(days), range_days=days)


class StatsExportView(CsvExportView):
    kind = 'stats'

    @extend_schema(operation_id='admin_stats_export', tags=TAGS, parameters=[RANGE_PARAM],
                   responses=CSV_RESPONSE)
    def get(self, request):
        days = _range(request, '7d')
        return self.send(request, admin_services.STATS_CSV_HEADER,
                         admin_services.stats_csv_rows(days), range_days=days)


class SiteFeedbackListView(AdminAPIView):
    @extend_schema(
        operation_id='admin_site_feedback_list',
        tags=TAGS,
        parameters=[
            OpenApiParameter('review_status', str, enum=SiteFeedback.Review.values),
            OpenApiParameter('kind', str, enum=SiteFeedback.Kind.values),
        ],
        responses=SiteFeedbackItemOut(many=True),
    )
    def get(self, request):
        items = admin_services.site_feedback_queryset(
            review_status=choice_param(request, 'review_status', SiteFeedback.Review.values),
            kind=choice_param(request, 'kind', SiteFeedback.Kind.values),
        )
        return paginate(self, items, admin_services.site_feedback_payload)


class SiteFeedbackDetailView(AdminAPIView):
    @extend_schema(operation_id='admin_site_feedback_review', tags=TAGS,
                   request=FeedbackReviewSerializer, responses=SiteFeedbackItemOut)
    def patch(self, request, feedback_id):
        item = get_object_or_404(SiteFeedback, pk=feedback_id)
        serializer = FeedbackReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_services.review_site_feedback(item, serializer.validated_data, user=request.user,
                                            request_id=request_id(request))
        item = admin_services.site_feedback_queryset().get(pk=item.pk)
        return Response(admin_services.site_feedback_payload(item))


class SettingsView(AdminAPIView):
    @extend_schema(operation_id='admin_settings_retrieve', tags=TAGS,
                   responses=SettingsSerializer)
    def get(self, request):
        return Response(SettingsSerializer(ChatSettings.load(fresh=True)).data)

    @extend_schema(operation_id='admin_settings_update', tags=TAGS,
                   request=SettingsSerializer, responses=SettingsSerializer)
    def patch(self, request):
        serializer = SettingsSerializer(ChatSettings.load(fresh=True), data=request.data,
                                        partial=True)
        serializer.is_valid(raise_exception=True)
        updated = admin_services.update_settings(serializer.validated_data, user=request.user,
                                                 request_id=request_id(request))
        return Response(SettingsSerializer(updated).data)


class PlaygroundView(AdminAPIView):
    @extend_schema(operation_id='admin_playground', tags=TAGS, request=PlaygroundSerializer,
                   responses=PlaygroundOut)
    def post(self, request):
        serializer = PlaygroundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        history = [dict(item) for item in data.get('history', [])]
        try:
            result = admin_services.playground(
                data['query'], user=request.user, history=history,
                rerank_enabled=data.get('rerank'),
            )
        except LLMError as exc:
            raise LLMUnavailable() from exc
        # The query is admin-typed but may quote a student; record its size, not its text.
        audit(request.user, 'playground.ran', 'playground', '-', request_id=request_id(request),
              query_chars=len(data['query']), llm_calls=result['usage']['llm_calls'],
              answer_type=result['answer_type'])
        return Response(result)
