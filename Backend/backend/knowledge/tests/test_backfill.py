from django.core.management import call_command
from django.core.management.base import CommandError
from rag.llm import QuotaExhausted, get_llm

from knowledge.ingest import backfill
from knowledge.ingest.chunk import ChunkDraft
from knowledge.ingest.pipeline import build_search_text, prepare_chunks
from knowledge.models import Chunk, Document, DocumentStatus, SourceType
from knowledge.tests.test_pipeline import KnowledgeTestCase, _Null


def stored_document(title, texts, *, context=''):
    """A READY document as the crawler import left it: no context in the search text."""
    document = Document.objects.create(
        title=title, source_type=SourceType.CRAWLER, content_hash=title,
        category='hostel_campus_life', status=DocumentStatus.READY, chunk_count=len(texts),
    )
    chunks = prepare_chunks(document, [ChunkDraft(t, '', None, None) for t in texts],
                            [context] * len(texts) if context else None)
    for chunk in chunks:
        chunk.embedding = [0.0] * 768
        chunk.is_searchable = True
    Chunk.objects.bulk_create(chunks)
    return document


def contexts(*sentences):
    return {'contexts': [{'index': i, 'context': s} for i, s in enumerate(sentences)]}


class BackfillTests(KnowledgeTestCase):
    def test_adds_context_to_search_text_and_re_embeds_only_those_chunks(self):
        document = stored_document('Boys Hostel', ['Hostel L has double rooms.', 'Hall B.'])
        before = {c.chunk_index: c.embedding for c in document.chunks.all()}
        self.fake.queue(contexts('Viyat Hall, formerly Hostel L, a boys hostel.', ''))

        stats = backfill.backfill_context(get_llm())

        self.assertEqual((stats.documents, stats.chunks, stats.model_calls), (1, 2, 1))
        first, second = document.chunks.order_by('chunk_index')
        self.assertIn('Viyat Hall, formerly Hostel L', first.search_text)
        self.assertEqual(first.content, 'Hostel L has double rooms.')  # students see no change
        self.assertNotEqual(list(first.embedding), list(before[0]))
        self.assertEqual(list(second.embedding), list(before[1]))  # no sentence, no re-embed
        self.assertEqual(self.fake.embed_calls[0][0], [first.search_text])
        self.assertEqual(len(self.changes), 1)  # the answer cache is told

    def test_a_second_run_does_nothing(self):
        stored_document('Boys Hostel', ['Hostel L has double rooms.'])
        self.fake.queue(contexts('Viyat Hall.'))
        backfill.backfill_context(get_llm())
        calls = len(self.fake.requests)

        stats = backfill.backfill_context(get_llm())

        self.assertEqual((stats.documents, stats.already_done), (0, 1))
        self.assertEqual(len(self.fake.requests), calls)

    def test_a_document_that_already_has_context_is_skipped(self):
        stored_document('Fees', ['Fee is 10.'], context='Hostel fee table.')
        stats = backfill.backfill_context(get_llm())
        self.assertEqual((stats.documents, stats.already_done), (0, 1))
        self.assertEqual(self.fake.requests, [])

    def test_pages_too_long_to_read_are_counted_and_skipped(self):
        count = backfill.CONTEXTUALIZE_MAX_CHUNKS + 1
        stored_document('Huge', [f'Part {n}.' for n in range(count)])
        stats = backfill.backfill_context(get_llm())
        self.assertEqual((stats.documents, stats.too_long), (0, 1))
        self.assertEqual(self.fake.requests, [])

    def test_long_pages_are_processed_on_request(self):
        count = backfill.CONTEXTUALIZE_MAX_CHUNKS + 1
        stored_document('Huge', [f'Part {n}.' for n in range(count)])
        stats = backfill.backfill_context(None, dry_run=True, include_long=True)
        self.assertEqual((stats.documents, stats.too_long, stats.model_calls), (1, 0, 16))

    def test_a_long_document_is_read_around_the_chunks_being_described(self):
        from knowledge.ingest import contextualize as module

        contents = [f'Section {n}. ' + 'x' * 2000 for n in range(60)]  # ~120,000 characters
        text = '\n\n'.join(contents)
        excerpt = module._excerpt(text, contents, 40, 10)
        self.assertLessEqual(len(excerpt), module.DOCUMENT_EXCERPT_CHARS + 200)
        self.assertTrue(excerpt.startswith('Section 0. '))  # the opening is always there
        for n in range(40, 50):
            self.assertIn(f'Section {n}. ', excerpt)
        self.assertIn('Section 39. ', excerpt)  # and the neighbours on both sides
        self.assertIn('Section 50. ', excerpt)
        self.assertNotIn('Section 20. ', excerpt)
        # A document that fits is read whole.
        self.assertEqual(module._excerpt('short', ['short'], 0, 1), 'short')

    def test_dry_run_counts_the_work_and_calls_nothing(self):
        stored_document('Boys Hostel', [f'Hall {n}.' for n in range(25)])
        stats = backfill.backfill_context(None, dry_run=True)
        self.assertEqual((stats.documents, stats.chunks, stats.model_calls), (1, 25, 3))
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(self.changes, [])

    def test_limit_and_title_filter(self):
        stored_document('Boys Hostel', ['A.'])
        stored_document('Girls Hostel', ['B.'])
        stored_document('Library', ['C.'])
        stats = backfill.backfill_context(None, dry_run=True, title_contains='hostel')
        self.assertEqual(stats.documents, 2)
        self.assertEqual(backfill.backfill_context(None, dry_run=True, limit=1).documents, 1)

    def test_a_used_up_quota_stops_the_run_but_keeps_finished_documents(self):
        stored_document('A first', ['One.'])
        stored_document('B second', ['Two.'])
        self.fake.queue(contexts('First page.'), QuotaExhausted('daily'))

        with self.assertRaises(QuotaExhausted):
            backfill.backfill_context(get_llm())

        done = Chunk.objects.filter(document__title='A first').get()
        self.assertIn('First page.', done.search_text)
        self.assertTrue(backfill.needs_context(Document.objects.get(title='B second'),
                                               Chunk.objects.get(document__title='B second')))
        self.assertEqual(len(self.changes), 1)  # the finished work still clears the cache

    def test_search_text_matches_what_a_fresh_import_would_store(self):
        document = stored_document('Boys Hostel', ['Hostel L has double rooms.'])
        self.fake.queue(contexts('Viyat Hall.'))
        backfill.backfill_context(get_llm())
        chunk = document.chunks.get()
        self.assertEqual(chunk.search_text,
                         build_search_text(document, chunk.content, '', 'Viyat Hall.'))


class ContextualizeCommandTests(KnowledgeTestCase):
    def test_dry_run_reports_and_changes_nothing(self):
        stored_document('Boys Hostel', ['Hostel L.'])
        out = _Null()
        call_command('contextualize_documents', '--dry-run', stdout=out)
        self.assertEqual(self.fake.requests, [])
        self.assertFalse(Chunk.objects.exclude(search_text__startswith='Boys Hostel').exists())

    def test_runs_and_stops_cleanly_on_quota(self):
        stored_document('Boys Hostel', ['Hostel L.'])
        self.fake.queue(QuotaExhausted('daily'))
        with self.assertRaises(CommandError):
            call_command('contextualize_documents', stdout=_Null())
