from api.models import AuditEvent
from django.test import TestCase
from rag.llm import QuotaExhausted, RetryableError, use_provider
from rag.llm.fake import FakeProvider
from userauths.models import User

from knowledge import services
from knowledge.ingest.filetypes import UnsupportedFile
from knowledge.ingest.pipeline import process_document
from knowledge.models import Chunk, Document, DocumentStatus, SourceType
from knowledge.signals import knowledge_changed
from knowledge.storage import MemoryStorage, use_storage
from knowledge.tests.factories import make_docx, make_pdf

FEES = (
    '# Hostel Fee Structure 2026-27\n\n'
    'All first year students must stay in the hostel. The fee is charged per year.\n\n'
    '| Hostel | Fee |\n|---|---|\n| Hall A | 1,20,000 |\n| Hall B | 1,10,000 |\n'
)


class KnowledgeTestCase(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        self.storage = MemoryStorage()
        use_provider(self.fake)
        use_storage(self.storage)
        self.addCleanup(use_provider, None)
        self.addCleanup(use_storage, None)
        self.admin = User.objects.create_user(email='admin@thapar.edu', is_staff=True)
        self.changes = []
        handler = lambda **kwargs: self.changes.append(kwargs)  # noqa: E731
        knowledge_changed.connect(handler, weak=False, dispatch_uid='test')
        self.addCleanup(knowledge_changed.disconnect, dispatch_uid='test')

    def text_document(self, text=FEES, **meta):
        with self.captureOnCommitCallbacks(execute=False):
            return services.create_from_text(
                title='Hostel fees',
                text=text,
                meta={'category': 'fees_scholarships', 'academic_year': '2026-27', **meta},
                user=self.admin,
            )


class PipelineTests(KnowledgeTestCase):
    def test_text_document_end_to_end(self):
        document = self.text_document()
        self.assertEqual(document.status, DocumentStatus.QUEUED)
        with self.captureOnCommitCallbacks(execute=True):
            document = process_document(document.pk)

        self.assertEqual(document.status, DocumentStatus.READY, document.error)
        chunks = list(document.chunks.all())
        self.assertEqual(document.chunk_count, len(chunks))
        self.assertTrue(all(c.is_searchable and c.embedding is not None for c in chunks))
        table = next(c for c in chunks if c.content.startswith('| Hostel'))
        self.assertEqual(table.heading_path, 'Hostel Fee Structure 2026-27')
        self.assertTrue(table.search_text.startswith('Hostel fees | Fees & scholarships'))
        self.assertEqual(table.category, 'fees_scholarships')
        self.assertTrue(self.changes)

    def test_claim_is_single_use(self):
        document = self.text_document()
        self.assertIsNotNone(process_document(document.pk))
        self.assertIsNone(process_document(document.pk))

    def test_pdf_upload(self):
        data = make_pdf([['Library Rules', 'The library opens at 8 am. ' * 12]] * 2)
        with self.captureOnCommitCallbacks(execute=False):
            document = services.create_from_upload(
                data=data, filename='library.pdf', meta={'category': 'rules_regulations'},
                user=self.admin,
            )
        self.assertEqual(document.title, 'library')
        self.assertEqual(document.page_count, 2)
        self.assertIn(document.storage_path, self.storage.objects)
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.READY, document.error)
        self.assertEqual(document.chunks.first().page_start, 1)

    def test_docx_upload(self):
        with self.captureOnCommitCallbacks(execute=False):
            document = services.create_from_upload(
                data=make_docx(), filename='rules.docx', meta={}, user=self.admin
            )
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.READY, document.error)
        self.assertEqual(document.source_type, SourceType.DOCX)

    def test_quota_exhaustion_fails_softly(self):
        document = self.text_document()
        self.fake.fail_next(QuotaExhausted('daily'))
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertIn('quota', document.error)
        self.assertFalse(document.chunks.exists())

    def test_reprocess_keeps_old_chunks_until_swap(self):
        document = process_document(self.text_document().pk)
        old_ids = set(document.chunks.values_list('pk', flat=True))
        with self.captureOnCommitCallbacks(execute=False):
            services.reprocess(document, user=self.admin)
        self.assertEqual(set(document.chunks.values_list('pk', flat=True)), old_ids)
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.READY)
        self.assertFalse(old_ids & set(document.chunks.values_list('pk', flat=True)))

    def test_unexpected_errors_do_not_leak(self):
        document = self.text_document()
        self.storage.objects.clear()
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertEqual(document.error, 'Could not read the original file from storage.')


class ServiceTests(KnowledgeTestCase):
    def test_duplicate_upload_is_rejected(self):
        self.text_document()
        with self.assertRaises(services.DuplicateDocument):
            self.text_document()

    def test_limits_and_types(self):
        with self.assertRaises(UnsupportedFile):
            services.create_from_upload(data=b'\x7fELF\x00', filename='x.pdf', meta={},
                                        user=self.admin)
        with self.settings(INGEST_MAX_PAGES=1), self.assertRaises(UnsupportedFile):
            services.create_from_upload(data=make_pdf([['a'], ['b']]), filename='x.pdf',
                                        meta={}, user=self.admin)

    def test_invalid_metadata_is_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.text_document(academic_year='2026')

    def test_url_outside_allowlist_is_rejected(self):
        from common.safe_http import UnsafeURLError

        with self.assertRaises(UnsafeURLError):
            services.create_from_url(url='https://example.com/', meta={}, user=self.admin)

    def test_metadata_update_syncs_chunks(self):
        document = process_document(self.text_document().pk)
        with self.captureOnCommitCallbacks(execute=False):
            services.update_document(document, {'is_current': False}, user=self.admin)
        self.assertFalse(document.chunks.filter(is_current=True).exists())
        self.assertEqual(document.status, DocumentStatus.READY)

    def test_title_change_requeues_for_reembedding(self):
        document = process_document(self.text_document().pk)
        with self.captureOnCommitCallbacks(execute=False):
            services.update_document(document, {'title': 'Hostel fees 2026'}, user=self.admin)
        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.QUEUED)

    def test_disable_and_enable(self):
        document = process_document(self.text_document().pk)
        services.set_enabled(document, False, user=self.admin)
        self.assertFalse(document.chunks.filter(is_searchable=True).exists())
        with self.assertRaises(services.InvalidTransition):
            services.set_enabled(document, False, user=self.admin)
        services.set_enabled(document, True, user=self.admin)
        self.assertFalse(document.chunks.filter(is_searchable=False).exists())

    def test_delete_removes_file_and_chunks(self):
        document = process_document(self.text_document().pk)
        path = document.storage_path
        services.delete_document(document, user=self.admin)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Chunk.objects.exists())
        self.assertNotIn(path, self.storage.objects)

    def test_every_change_is_audited(self):
        document = process_document(self.text_document().pk)
        services.set_enabled(document, False, user=self.admin)
        services.delete_document(document, user=self.admin)
        actions = list(AuditEvent.objects.values_list('action', flat=True).order_by('created_at'))
        self.assertEqual(actions, ['document.created', 'document.disabled', 'document.deleted'])
