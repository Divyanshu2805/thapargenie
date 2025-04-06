from rest_framework import status
from rest_framework.exceptions import APIException


class UnsupportedFileError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'This file type is not supported.'
    default_code = 'unsupported_file'


class FileTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = 'The upload is too large.'
    default_code = 'file_too_large'


class TooManyFiles(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Upload at most 10 files at a time.'
    default_code = 'too_many_files'


class UrlNotAllowed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Only https pages on the allowed college domains can be added.'
    default_code = 'url_not_allowed'


class InvalidTransitionError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'The document cannot do that in its current state.'
    default_code = 'invalid_transition'


class StorageUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'File storage is unavailable right now. Try again shortly.'
    default_code = 'storage_unavailable'


class LLMUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'The language model is unavailable right now. Try again shortly.'
    default_code = 'llm_unavailable'
