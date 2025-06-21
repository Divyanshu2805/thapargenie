from rest_framework import status
from rest_framework.exceptions import APIException


class ConversationBusy(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'An answer is still being written. Wait for it or stop it first.'
    default_code = 'conversation_busy'


class ConversationFull(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This conversation is full. Please start a new one.'
    default_code = 'conversation_full'


class InvalidParent(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'That message cannot be edited or regenerated.'
    default_code = 'invalid_parent'


class DailyQuotaExceeded(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "You've reached today's question limit. It resets at midnight."
    default_code = 'daily_quota_exceeded'


class ServiceBusy(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'ThaparGenie is very busy right now. Please try again later.'
    default_code = 'service_busy'
