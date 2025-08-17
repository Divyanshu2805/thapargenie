import json

import httpx
from django.test import SimpleTestCase

from knowledge.storage import StorageError, SupabaseStorage


class SupabaseStorageTests(SimpleTestCase):
    """The REST calls, against a mocked transport (no network)."""

    def storage(self, handler):
        self.requests = []

        def record(request):
            self.requests.append(request)
            return handler(request)

        storage = SupabaseStorage('https://project.supabase.co', 'service-key', 'documents')
        storage._client = httpx.Client(transport=httpx.MockTransport(record),
                                       headers=storage._client.headers)
        return storage

    def test_upload_sends_the_type_and_the_service_key(self):
        storage = self.storage(lambda request: httpx.Response(200, json={}))
        storage.upload('documents/a b.pdf', b'%PDF', 'application/pdf')
        request = self.requests[0]
        self.assertEqual(str(request.url),
                         'https://project.supabase.co/storage/v1/object/documents/documents/a%20b.pdf')
        self.assertEqual(request.headers['content-type'], 'application/pdf')
        self.assertEqual(request.headers['authorization'], 'Bearer service-key')

    def test_errors_never_leak_the_response_body(self):
        storage = self.storage(lambda request: httpx.Response(403, text='secret detail'))
        with self.assertRaises(StorageError) as caught:
            storage.download('documents/a.pdf')
        self.assertEqual(str(caught.exception), 'Storage download failed with HTTP 403.')

    def test_delete_skips_empty_paths_and_sends_prefixes(self):
        storage = self.storage(lambda request: httpx.Response(200, json=[]))
        storage.delete(['', None])
        self.assertEqual(self.requests, [])
        storage.delete(['documents/a.pdf', ''])
        self.assertEqual(json.loads(self.requests[0].content), {'prefixes': ['documents/a.pdf']})

    def test_list_pages_through_everything_and_skips_folders(self):
        page_one = [{'id': str(i), 'name': f'{i}.pdf', 'created_at': '2026-01-01T00:00:00Z'}
                    for i in range(2)]
        # A full page means there may be more: the empty third page ends the walk.
        pages = [page_one, [{'id': None, 'name': 'nested'}, {'id': 'x', 'name': 'x.pdf'}], []]

        def handler(request):
            body = json.loads(request.content)
            return httpx.Response(200, json=pages[body['offset'] // body['limit']])

        found = self.storage(handler).list('documents', page_size=2)
        self.assertEqual(sorted(found), ['documents/0.pdf', 'documents/1.pdf', 'documents/x.pdf'])
        self.assertEqual(found['documents/x.pdf'], '')
        self.assertEqual([json.loads(r.content)['offset'] for r in self.requests], [0, 2, 4])

    def test_signed_url_requires_a_url_in_the_reply(self):
        storage = self.storage(lambda request: httpx.Response(200, json={}))
        with self.assertRaises(StorageError):
            storage.signed_url('documents/a.pdf')
