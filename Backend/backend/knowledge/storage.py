"""Private file storage for uploaded originals (Supabase Storage REST API)."""

import threading
from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

SIGNED_URL_SECONDS = 600


class StorageError(Exception):
    pass


class SupabaseStorage:
    def __init__(self, url, key, bucket, timeout=30.0):
        self.base = f'{url}/storage/v1'
        self.bucket = bucket
        self._client = httpx.Client(
            timeout=timeout,
            headers={'apikey': key, 'Authorization': f'Bearer {key}'},
        )

    def _object_url(self, path):
        return f'{self.base}/object/{self.bucket}/{quote(path)}'

    def _check(self, response, action):
        if response.status_code >= 400:
            raise StorageError(f'Storage {action} failed with HTTP {response.status_code}.')
        return response

    def upload(self, path, data, content_type):
        response = self._client.post(
            self._object_url(path),
            content=data,
            headers={'content-type': content_type, 'x-upsert': 'true'},
        )
        self._check(response, 'upload')

    def download(self, path):
        return self._check(self._client.get(self._object_url(path)), 'download').content

    def delete(self, paths):
        paths = [path for path in paths if path]
        if not paths:
            return
        response = self._client.request(
            'DELETE', f'{self.base}/object/{self.bucket}', json={'prefixes': paths}
        )
        self._check(response, 'delete')

    def signed_url(self, path, *, filename=None, expires=SIGNED_URL_SECONDS):
        response = self._check(
            self._client.post(
                f'{self.base}/object/sign/{self.bucket}/{quote(path)}',
                json={'expiresIn': expires},
            ),
            'sign',
        )
        signed = response.json().get('signedURL')
        if not signed:
            raise StorageError('Storage did not return a signed URL.')
        # `download` makes Storage send Content-Disposition: attachment. Always set it, so
        # an uploaded HTML file is saved, never rendered, when an admin or student opens it.
        name = filename or path.rsplit('/', 1)[-1]
        return f'{self.base}{signed}&download={quote(name)}'


class MemoryStorage:
    """In-process storage for tests."""

    def __init__(self):
        self.objects = {}

    def upload(self, path, data, content_type):
        self.objects[path] = (data, content_type)

    def download(self, path):
        if path not in self.objects:
            raise StorageError('Not found.')
        return self.objects[path][0]

    def delete(self, paths):
        for path in paths:
            self.objects.pop(path, None)

    def signed_url(self, path, *, filename=None, expires=SIGNED_URL_SECONDS):
        return f'memory://{path}?expires={expires}'


_storage = None
_lock = threading.Lock()


def use_storage(storage):
    global _storage
    _storage = storage


def get_storage():
    global _storage
    with _lock:
        if _storage is None:
            if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
                raise ImproperlyConfigured(
                    'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.'
                )
            _storage = SupabaseStorage(
                settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, settings.SUPABASE_BUCKET
            )
        return _storage
