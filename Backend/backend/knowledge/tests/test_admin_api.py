from api.models import AuditEvent
from chat.models import AnswerCache, ChatSettings
from common.tests.helpers import client_for, make_user
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rag.llm import LLMError, use_provider
from rag.llm.fake import FakeProvider, hashed_embedding

from knowledge import services
from knowledge.ingest.chunk import ChunkDraft
from knowledge.ingest.pipeline import prepare_chunks
from knowledge.models import Chunk, Document, DocumentStatus, Parser
from knowledge.signals import knowledge_changed
from knowledge.storage import MemoryStorage, use_storage
from knowledge.tests.factories import make_pdf

BASE = '/api/v1/admin'


def pdf_file(name='fees.pdf', lines=('Hostel fee is Rs 1,20,000.',)):
    return SimpleUploadedFile(name, make_pdf([list(lines)]), content_type='application/pdf')


class AdminKnowledgeTestCase(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        self.storage = MemoryStorage()
        use_provider(self.fake)
        use_storage(self.storage)
        self.addCleanup(use_provider, None)
        self.addCleanup(use_storage, None)
        ChatSettings.forget()
        self.addCleanup(ChatSettings.forget)
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.client = client_for(self.admin)
        self.changes = []
        knowledge_changed.connect(lambda **kw: self.changes.append(kw), weak=False,
                                  dispatch_uid='admin-test')
        self.addCleanup(knowledge_changed.disconnect, dispatch_uid='admin-test')

    def ready_document(self, title='Hostel fees', text='Boys hostel fee is Rs 1,20,000.'):
        with self.captureOnCommitCallbacks(execute=False):
            document = services.create_from_text(
                title=title, text=text, meta={'category': 'fees_scholarships'}, user=self.admin
            )
        chunks = prepare_chunks(document, [ChunkDraft(text, 'Fees', 1, 1)])
        for chunk in chunks:
            chunk.embedding = hashed_embedding(chunk.search_text, 768)
            chunk.is_searchable = True
            chunk.token_count = 10
        Chunk.objects.bulk_create(chunks)
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.READY, chunk_count=1, token_count=10
        )
        document.refresh_from_db()
        return document

    def upload(self, *files, **fields):
        with self.captureOnCommitCallbacks(execute=False):
            return self.client.post(f'{BASE}/documents/', {'files': list(files), **fields},
                                    format='multipart')

    def audited(self, action):
        return AuditEvent.objects.filter(action=action, actor=self.admin).exists()


class UploadTests(AdminKnowledgeTestCase):
    def test_upload_queues_documents_with_metadata(self):
        response = self.upload(pdf_file(), category='fees_scholarships',
                               academic_year='2026-27', is_current='false', parser='smart')
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data['rejected'], [])
        [created] = response.data['created']
        self.assertEqual(created['title'], 'fees')
        self.assertEqual(created['status'], 'queued')
        self.assertEqual(created['page_count'], 1)
        self.assertNotIn('storage_path', created)
        document = Document.objects.get(pk=created['id'])
        self.assertEqual((document.category, document.academic_year, document.is_current,
                          document.parser), ('fees_scholarships', '2026-27', False, 'smart'))
        self.assertIn(document.storage_path, self.storage.objects)
        self.assertTrue(self.audited('document.created'))

    def test_contextualize_defaults_to_the_setting(self):
        ChatSettings.objects.update_or_create(pk=1, defaults={'contextualize_default': True})
        ChatSettings.forget()
        response = self.upload(pdf_file())
        self.assertTrue(response.data['created'][0]['contextualize'])
        response = self.upload(pdf_file('b.pdf', ['Other text.']), contextualize='false')
        self.assertFalse(response.data['created'][0]['contextualize'])

    def test_wrong_magic_bytes_are_rejected(self):
        fake_pdf = SimpleUploadedFile('fees.pdf', b'\x7fELF\x00\x00binary', 'application/pdf')
        response = self.upload(fake_pdf)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'unsupported_file')
        self.assertFalse(Document.objects.exists())

    @override_settings(INGEST_MAX_FILE_MB=1)
    def test_too_large_file_is_rejected(self):
        big = SimpleUploadedFile('big.pdf', make_pdf([['x']]) + b' ' * (1024 * 1024 + 1))
        response = self.upload(big)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data['error']['code'], 'file_too_large')

    def test_too_many_files_are_rejected(self):
        files = [pdf_file(f'{n}.pdf', [f'Line {n}.']) for n in range(11)]
        response = self.upload(*files)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'too_many_files')
        self.assertFalse(Document.objects.exists())

    def test_missing_files_and_unknown_fields_are_rejected(self):
        self.assertEqual(self.upload().status_code, 400)
        response = self.upload(pdf_file(), owner='someone')
        self.assertEqual(response.status_code, 400)
        self.assertIn('owner', response.data['error']['fields'])

    def test_duplicate_points_at_the_existing_document(self):
        first = self.upload(pdf_file()).data['created'][0]
        response = self.upload(pdf_file())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'duplicate_document')
        self.assertEqual(response.data['error']['existing_id'], first['id'])

    def test_partial_batch_reports_rejected_files(self):
        self.upload(pdf_file())
        response = self.upload(pdf_file(), pdf_file('new.pdf', ['New text.']))
        self.assertEqual(response.status_code, 202)
        self.assertEqual([d['title'] for d in response.data['created']], ['new'])
        [rejected] = response.data['rejected']
        self.assertEqual((rejected['filename'], rejected['code']),
                         ('fees.pdf', 'duplicate_document'))
        self.assertNotIn('status', rejected)


class AddTests(AdminKnowledgeTestCase):
    def test_add_text(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(f'{BASE}/documents/text/', {
                'title': 'Library FAQ', 'text': 'The library opens at 8 am.',
                'category': 'faq',
            }, format='json')
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data['source_type'], 'text')
        self.assertTrue(self.audited('document.created'))

    def test_add_url_outside_the_allowlist_is_refused(self):
        response = self.client.post(f'{BASE}/documents/url/',
                                    {'url': 'https://example.com/page'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'url_not_allowed')

    def test_http_source_url_is_refused(self):
        response = self.client.post(f'{BASE}/documents/text/', {
            'title': 'x', 'text': 'y', 'source_url': 'http://www.thapar.edu/',
        }, format='json')
        self.assertEqual(response.status_code, 400)


class DocumentTests(AdminKnowledgeTestCase):
    def test_list_filters(self):
        ready = self.ready_document()
        with self.captureOnCommitCallbacks(execute=False):
            services.create_from_text(title='Calendar', text='Mid sems in October.',
                                      meta={'category': 'academic_calendar'}, user=self.admin)
        response = self.client.get(f'{BASE}/documents/', {'status': 'ready'})
        self.assertEqual([d['id'] for d in response.data['results']], [str(ready.pk)])
        response = self.client.get(f'{BASE}/documents/', {'q': 'calen'})
        self.assertEqual([d['title'] for d in response.data['results']], ['Calendar'])
        response = self.client.get(f'{BASE}/documents/', {'category': 'faq'})
        self.assertEqual(response.data['results'], [])
        response = self.client.get(f'{BASE}/documents/', {'status': ''})
        self.assertEqual(len(response.data['results']), 2)

    def test_list_refuses_unknown_filter_values(self):
        for name in ('status', 'category', 'source_type'):
            response = self.client.get(f'{BASE}/documents/', {name: 'nope'})
            self.assertEqual(response.status_code, 400, name)
            self.assertIn(name, response.data['error']['fields'])

    def test_patch_updates_metadata_and_chunks(self):
        document = self.ready_document()
        response = self.client.patch(f'{BASE}/documents/{document.pk}/',
                                     {'is_current': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Chunk.objects.get(document=document).is_current)
        self.assertTrue(self.audited('document.updated'))

    def test_patch_rejects_invalid_values(self):
        document = self.ready_document()
        for body in ({'academic_year': '2026'}, {'category': 'nope'}, {'status': 'ready'}):
            response = self.client.patch(f'{BASE}/documents/{document.pk}/', body,
                                         format='json')
            self.assertEqual(response.status_code, 400, body)

    def test_disable_enable_and_invalid_transition(self):
        document = self.ready_document()
        response = self.client.post(f'{BASE}/documents/{document.pk}/disable/')
        self.assertEqual(response.data['status'], 'disabled')
        self.assertFalse(Chunk.objects.get(document=document).is_searchable)
        response = self.client.post(f'{BASE}/documents/{document.pk}/disable/')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'invalid_transition')
        response = self.client.post(f'{BASE}/documents/{document.pk}/enable/')
        self.assertEqual(response.data['status'], 'ready')
        self.assertTrue(self.audited('document.disabled'))
        self.assertTrue(self.audited('document.enabled'))

    def test_reprocess_can_force_smart_parsing(self):
        document = self.ready_document()
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(f'{BASE}/documents/{document.pk}/reprocess/',
                                        {'parser': 'smart'}, format='json')
        self.assertEqual(response.status_code, 202)
        document.refresh_from_db()
        self.assertEqual((document.status, document.parser), ('queued', Parser.SMART))
        response = self.client.post(f'{BASE}/documents/{document.pk}/reprocess/')
        self.assertEqual(response.status_code, 409)
        event = AuditEvent.objects.get(action='document.reprocessed')
        self.assertEqual(event.metadata['parser'], 'smart')

    def test_delete_removes_row_and_file(self):
        document = self.ready_document()
        path = document.storage_path
        response = self.client.delete(f'{BASE}/documents/{document.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
        self.assertNotIn(path, self.storage.objects)
        self.assertTrue(self.audited('document.deleted'))

    def test_file_is_a_signed_url(self):
        document = self.ready_document()
        response = self.client.get(f'{BASE}/documents/{document.pk}/file/')
        self.assertEqual(response.data['url'], f'memory://{document.storage_path}?expires=600')
        self.assertTrue(self.audited('document.file_opened'))

    def test_unknown_document_is_404(self):
        response = self.client.get(f'{BASE}/documents/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)


class ChunkTests(AdminKnowledgeTestCase):
    def test_list_chunks(self):
        document = self.ready_document()
        response = self.client.get(f'{BASE}/documents/{document.pk}/chunks/')
        [chunk] = response.data['results']
        self.assertEqual((chunk['chunk_index'], chunk['heading_path']), (0, 'Fees'))
        self.assertNotIn('embedding', chunk)

    def test_edit_re_embeds_and_clears_the_answer_cache(self):
        document = self.ready_document()
        chunk = Chunk.objects.get(document=document)
        AnswerCache.objects.create(query_text='q', query_embedding=[0.1] * 768, answer='a',
                                   expires_at='2100-01-01T00:00:00Z')
        text = 'Girls hostel fee is Rs 1,30,000 per year.'
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(f'{BASE}/chunks/{chunk.pk}/', {'content': text},
                                         format='json')
        self.assertEqual(response.status_code, 200, response.data)
        chunk.refresh_from_db()
        self.assertEqual(chunk.content, text)
        self.assertIn('Girls hostel fee', chunk.search_text)
        self.assertIn('Hostel fees', chunk.search_text)  # the document header is kept
        self.assertEqual([calls for calls, _ in self.fake.embed_calls], [[chunk.search_text]])
        expected = hashed_embedding(chunk.search_text, 768)
        similarity = sum(a * b for a, b in zip(chunk.embedding, expected, strict=True))
        self.assertGreater(similarity, 0.999)  # halfvec storage rounds each value
        self.assertEqual(len(self.changes), 1)
        self.assertFalse(AnswerCache.objects.exists())
        self.assertTrue(self.audited('chunk.updated'))

    def test_unchanged_edit_does_nothing(self):
        document = self.ready_document()
        chunk = Chunk.objects.get(document=document)
        response = self.client.patch(f'{BASE}/chunks/{chunk.pk}/',
                                     {'content': chunk.content}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake.embed_calls, [])
        self.assertFalse(self.audited('chunk.updated'))

    def test_edit_fails_cleanly_when_the_llm_is_down(self):
        document = self.ready_document()
        chunk = Chunk.objects.get(document=document)
        self.fake.fail_next(LLMError('down'))
        response = self.client.patch(f'{BASE}/chunks/{chunk.pk}/', {'content': 'New.'},
                                     format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'llm_unavailable')
        chunk.refresh_from_db()
        self.assertNotEqual(chunk.content, 'New.')

    def test_edit_is_refused_while_processing(self):
        document = self.ready_document()
        Document.objects.filter(pk=document.pk).update(status=DocumentStatus.PROCESSING)
        chunk = Chunk.objects.get(document=document)
        response = self.client.patch(f'{BASE}/chunks/{chunk.pk}/', {'content': 'x'},
                                     format='json')
        self.assertEqual(response.status_code, 409)

    def test_empty_chunk_is_refused(self):
        chunk = Chunk.objects.get(document=self.ready_document())
        response = self.client.patch(f'{BASE}/chunks/{chunk.pk}/', {'content': '   '},
                                     format='json')
        self.assertEqual(response.status_code, 400)

    def test_delete_chunk_updates_counts(self):
        document = self.ready_document()
        chunk = Chunk.objects.get(document=document)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f'{BASE}/chunks/{chunk.pk}/')
        self.assertEqual(response.status_code, 204)
        document.refresh_from_db()
        self.assertEqual((document.chunk_count, document.token_count), (0, 0))
        self.assertEqual(len(self.changes), 1)
        self.assertTrue(self.audited('chunk.deleted'))
