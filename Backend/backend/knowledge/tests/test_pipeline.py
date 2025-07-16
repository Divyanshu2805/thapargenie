import gzip
import json
import tempfile
from pathlib import Path

from api.models import AuditEvent
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rag.llm import QuotaExhausted, RetryableError, use_provider
from rag.llm.fake import FakeProvider
from userauths.models import User

from knowledge import services
from knowledge.ingest import crawler_import
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
        self.assertIn('halls of residence', table.search_text)  # alias expansion
        self.assertEqual(table.category, 'fees_scholarships')
        self.assertTrue(self.changes)

    def test_full_text_column_is_populated(self):
        document = process_document(self.text_document().pk)
        hit = Chunk.objects.filter(document=document, fts='hostel').exists()
        self.assertTrue(hit)

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

    def test_contextualize_adds_sentence_to_search_text(self):
        document = self.text_document(contextualize=True)
        self.fake.queue({'contexts': [{'index': 0, 'context': 'Intro to boys hostel fees.'},
                                      {'index': 1, 'context': 'Fee table for 2026-27.'}]})
        document = process_document(document.pk)
        texts = [c.search_text for c in document.chunks.all()]
        self.assertTrue(any('Fee table for 2026-27.' in text for text in texts))
        self.assertFalse(any('Fee table' in c.content for c in document.chunks.all()))

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


def write_export(folder, rows):
    path = Path(folder) / 'chunks.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row) + '\n')
    return path


def row(record, index, text, category='hostel_campus_life', status='keep', **meta):
    return {
        'chunk_id': f'{record}-{index}',
        'record_id': record,
        'chunk_index': index,
        'text': text,
        'metadata': {
            'url': f'https://www.thapar.edu/{record}',
            'title': meta.pop('title', f'{record} 2026-27'),
            'category': category,
            'status': status,
            'is_current': True,
            'date': '2026-05-12',
            'department': None,
            **meta,
        },
    }


class CrawlerImportTests(KnowledgeTestCase):
    def export(self, rows):
        folder = tempfile.mkdtemp()
        write_export(folder, rows)
        return folder

    def test_import_groups_records_and_is_resumable(self):
        folder = self.export([
            row('hostel', 1, 'Hostels | Campus life\n\n[page 2]\nHall B fee is 1,10,000.'),
            row('hostel', 0, 'Hostels | Campus life\n\n[page 1]\nHall A fee is 1,20,000.'),
            row('news', 0, 'Won a prize.', category='news_events'),
            row('draft', 0, 'Unreviewed.', status='review'),
        ])
        call_command('import_crawler_export', folder, stdout=_Null())
        document = Document.objects.get()
        self.assertEqual(document.source_type, SourceType.CRAWLER)
        self.assertEqual(document.academic_year, '2026-27')
        self.assertEqual(document.metadata['record_id'], 'hostel')
        chunks = list(document.chunks.order_by('chunk_index'))
        self.assertEqual([c.content for c in chunks],
                         ['Hall A fee is 1,20,000.', 'Hall B fee is 1,10,000.'])
        self.assertEqual((chunks[1].page_start, chunks[1].page_end), (2, 2))
        self.assertTrue(all(c.is_searchable and c.embedding is not None for c in chunks))

        calls = len(self.fake.embed_calls)
        call_command('import_crawler_export', folder, stdout=_Null())
        self.assertEqual(len(self.fake.embed_calls), calls)  # nothing re-embedded

    def test_changed_record_replaces_old_version(self):
        call_command('import_crawler_export', self.export([row('fee', 0, 'Fee is 10.')]),
                     stdout=_Null())
        call_command('import_crawler_export', self.export([row('fee', 0, 'Fee is 12.')]),
                     stdout=_Null())
        document = Document.objects.get()
        self.assertEqual(document.chunks.get().content, 'Fee is 12.')

    def test_embeddings_are_batched_across_records(self):
        rows = [row(f'r{n}', 0, f'Text {n}.') for n in range(6)]
        records = crawler_import.read_records(
            write_export(tempfile.mkdtemp(), rows), categories={'hostel_campus_life'}
        )
        from rag.llm import get_llm

        crawler_import.import_records(records, get_llm(embed_batch_size=50), batch_texts=100)
        self.assertEqual(len(self.fake.embed_calls), 1)

    def test_quota_stop_keeps_finished_records(self):
        rows = [row(f'r{n}', 0, f'Text {n}.') for n in range(4)]
        folder = self.export(rows)
        records = crawler_import.read_records(Path(folder) / 'chunks.jsonl.gz',
                                              categories={'hostel_campus_life'})
        from rag.llm import get_llm

        llm = get_llm(embed_batch_size=2)
        self.fake.embed = _fail_after(self.fake.embed, calls=1)
        with self.assertRaises(QuotaExhausted):
            crawler_import.import_records(records, llm, batch_texts=2)
        self.assertEqual(Document.objects.filter(status=DocumentStatus.READY).count(), 2)

    def test_dry_run_calls_no_api(self):
        call_command('import_crawler_export', self.export([row('a', 0, 'x')]), '--dry-run',
                     stdout=_Null())
        self.assertFalse(Document.objects.exists())
        self.assertEqual(self.fake.embed_calls, [])

    def test_missing_file(self):
        with self.assertRaises(CommandError):
            call_command('import_crawler_export', tempfile.mkdtemp(), stdout=_Null())

    def test_transient_errors_are_retried(self):
        self.fake.fail_next(RetryableError('busy', retry_after=0))
        call_command('import_crawler_export', self.export([row('a', 0, 'x y z')]),
                     stdout=_Null())
        self.assertEqual(Document.objects.get().status, DocumentStatus.READY)


def _fail_after(embed, calls):
    state = {'n': 0}

    def wrapper(*args, **kwargs):
        state['n'] += 1
        if state['n'] > calls:
            raise QuotaExhausted('daily')
        return embed(*args, **kwargs)

    return wrapper


class _Null:
    def write(self, *args, **kwargs):
        pass

    def flush(self):
        pass
