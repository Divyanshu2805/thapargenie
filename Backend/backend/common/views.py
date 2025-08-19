"""Browser error reports.

The SPA posts uncaught errors here so they reach the same logs (and Sentry, when
enabled) as server errors. Signed-out pages can report too, so the endpoint accepts
anonymous requests; the throttle counts per user or per address, and every field is
length-capped and never echoed back.
"""

import logging
import re

from api.serializers import RejectUnknownFieldsMixin
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import ClientErrorThrottle

logger = logging.getLogger('thapargpt.client')

# Emails and long digit runs (phone or roll numbers) sometimes end up in error messages.
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_DIGITS = re.compile(r'\d{6,}')


def scrub(text):
    return _DIGITS.sub('[number]', _EMAIL.sub('[email]', text))


class ClientErrorSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    message = serializers.CharField(max_length=500)
    stack = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    # A path only: the SPA strips the query string and fragment before sending.
    path = serializers.RegexField(r'^/[\w\-./]{0,200}$', required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=('render', 'error', 'rejection', 'chunk'),
                                   default='error')
    release = serializers.CharField(max_length=40, required=False, allow_blank=True)


class ClientErrorView(APIView):
    # Reports are sent without a token (the page may be signed out or broken), so there
    # is nothing to authenticate and no Firebase call per report.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ClientErrorThrottle]

    @extend_schema(operation_id='client_error_report', tags=['ops'],
                   request=ClientErrorSerializer, responses={204: None})
    def post(self, request):
        serializer = ClientErrorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        logger.warning(
            'Browser %s on %s: %s', data['kind'], data.get('path') or '-',
            scrub(data['message']),
            extra={'client_stack': scrub(data.get('stack', ''))[:4000],
                   'client_release': data.get('release', '')},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
