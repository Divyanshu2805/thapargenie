"""Security regression tests that cut across apps.

SSRF, throttles and admin permissions have their own suites (test_safe_http,
test_throttles, test_admin_api); this file covers the remaining gaps.
"""

import io
import json
import uuid

import httpx
from chat.models import Conversation, Feedback, Message
from chat.tests.test_chat import ChatTestCase, approved_user, client_for
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from knowledge.models import Document
from knowledge.storage import SupabaseStorage
from knowledge.tests.factories import make_pdf
from knowledge.tests.test_admin_api import AdminKnowledgeTestCase
from pypdf import PdfReader, PdfWriter

from common.headers import API_CSP


class SignedUrlTests(TestCase):
    def signed(self, filename):
        storage = SupabaseStorage('https://project.supabase.co', 'key', 'documents')
        storage._client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'signedURL': '/object/sign/x?token=t'})
        ))
        return storage.signed_url('documents/abc.html', filename=filename)

    def test_signed_links_always_force_a_download(self):
        self.assertTrue(self.signed(None).endswith('&download=abc.html'))
        self.assertTrue(self.signed('Fee notice.pdf').endswith('&download=Fee%20notice.pdf'))


class ResponseHeaderTests(TestCase):
    def test_api_responses_forbid_rendering_as_a_page(self):
        for path in ('/health/live/', '/api/v1/me/', '/api/v1/conversations/'):
            response = self.client.get(path)
            self.assertEqual(response['Content-Security-Policy'], API_CSP, path)
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff', path)
            self.assertEqual(response['X-Frame-Options'], 'DENY', path)
            self.assertIn('camera=()', response['Permissions-Policy'])

    def test_request_id_is_echoed_only_when_it_is_a_uuid(self):
        good = str(uuid.uuid4())
        self.assertEqual(self.client.get('/health/live/', HTTP_X_REQUEST_ID=good)['X-Request-ID'],
                         good)
        forged = self.client.get('/health/live/', HTTP_X_REQUEST_ID='<script>x</script>')
        self.assertNotIn('script', forged['X-Request-ID'])
        uuid.UUID(forged['X-Request-ID'])

    def test_cors_preflight_allows_the_request_id_header(self):
        response = self.client.options(
            '/api/v1/me/', HTTP_ORIGIN='http://localhost:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization, x-request-id',
        )
        allowed = response['Access-Control-Allow-Headers'].lower()
        self.assertIn('x-request-id', allowed)
        self.assertIn('authorization', allowed)


class OwnershipGapTests(ChatTestCase):
    """IDOR cases not in chat.tests.OwnershipTests: every foreign id must look like a 404."""

    def setUp(self):
        super().setUp()
        self.victim_conversation = self.conversation()
        self.answered(self.victim_conversation)
        self.victim_answer = Message.objects.get(role=Message.Role.ASSISTANT)
        self.victim_question = self.victim_answer.parent
        Feedback.objects.create(message=self.victim_answer, user=self.user, rating=-1)
        self.intruder = approved_user('intruder@thapar.edu')
        self.intruder_client = client_for(self.intruder)
        self.own = Conversation.objects.create(user=self.intruder)

    def test_cannot_delete_someone_elses_feedback(self):
        path = f'/api/v1/messages/{self.victim_answer.pk}/feedback/'
        response = self.intruder_client.delete(path)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Feedback.objects.filter(message=self.victim_answer).exists())

    def test_cannot_point_own_conversation_at_someone_elses_message(self):
        response = self.intruder_client.patch(
            f'/api/v1/conversations/{self.own.pk}/',
            {'current_leaf_id': str(self.victim_answer.pk)}, format='json',
        )
        self.assertEqual(response.status_code, 404)
        self.own.refresh_from_db()
        self.assertIsNone(self.own.current_leaf_id)

    def test_cannot_branch_from_someone_elses_question(self):
        response = self.ask(self.own, client=self.intruder_client,
                            edit_of=str(self.victim_question.pk))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Message.objects.filter(conversation=self.own).exists())

    def test_export_contains_only_own_conversations(self):
        response = self.intruder_client.get('/api/v1/me/export/')
        exported = [c['id'] for c in json.loads(response.content)['conversations']]
        self.assertEqual(exported, [str(self.own.pk)])

    def test_delete_all_only_touches_own_conversations(self):
        self.intruder_client.delete('/api/v1/conversations/')
        self.assertTrue(Conversation.objects.filter(pk=self.victim_conversation.pk).exists())
        self.assertFalse(Conversation.objects.filter(user=self.intruder).exists())


class UploadHardeningTests(AdminKnowledgeTestCase):
    def test_password_protected_pdf_is_rejected_at_upload(self):
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf([['Secret fees.']]))))
        # A throwaway test fixture, not a credential.
        writer.encrypt(user_password='letmein', owner_password='owner')  # noqa: S106
        data = io.BytesIO()
        writer.write(data)
        response = self.upload(SimpleUploadedFile('locked.pdf', data.getvalue(), 'application/pdf'))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'unsupported_file')
        self.assertIn('Password-protected', response.data['error']['message'])
        self.assertFalse(Document.objects.exists())

    def test_type_comes_from_content_not_the_name(self):
        # HTML uploads are allowed, but a .pdf name must not make them a PDF.
        disguised = SimpleUploadedFile('fees.pdf', b'<html><body>Fees</body></html>',
                                       'application/pdf')
        response = self.upload(disguised)
        self.assertEqual(response.status_code, 202)
        document = Document.objects.get()
        self.assertEqual((document.source_type, document.mime_type), ('html', 'text/html'))
        self.assertTrue(document.storage_path.endswith('.html'))

    def test_stored_files_get_random_keys_not_the_uploaded_name(self):
        response = self.upload(SimpleUploadedFile('../../etc/passwd.pdf', make_pdf([['Fees.']]),
                                                  'application/pdf'))
        self.assertEqual(response.status_code, 202)
        document = Document.objects.get()
        self.assertRegex(document.storage_path, r'^documents/[0-9a-f-]{36}\.pdf$')
        self.assertEqual(list(self.storage.objects), [document.storage_path])
