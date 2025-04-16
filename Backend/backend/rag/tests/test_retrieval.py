import hashlib

from django.test import SimpleTestCase, TestCase
from knowledge.ingest.chunk import ChunkDraft
from knowledge.ingest.pipeline import prepare_chunks
from knowledge.models import Chunk, Document, DocumentStatus, SourceType

from rag.context import build_sources
from rag.llm import use_provider
from rag.llm.client import LLM
from rag.llm.fake import FakeProvider, hashed_embedding
from rag.pipeline import NOT_FOUND, AnswerType, answer, answer_events, cited_numbers
from rag.retrieve import Candidate, fuse, retrieve


def make_llm(fake):
    return LLM(
        chat_provider=fake,
        embed_provider=fake,
        chat_model='chat',
        fast_model='fast',
        embed_model='embed',
        sleep=lambda _s: None,
    )


def add_document(title, contents, *, category='fees_scholarships', year='', current=True,
                 searchable=True, url=''):
    document = Document.objects.create(
        title=title,
        source_type=SourceType.TEXT,
        source_url=url,
        content_hash=hashlib.sha256(title.encode()).hexdigest(),
        category=category,
        academic_year=year,
        is_current=current,
        status=DocumentStatus.READY,
    )
    chunks = prepare_chunks(document, [ChunkDraft(text, '', None, None) for text in contents])
    for chunk in chunks:
        chunk.embedding = hashed_embedding(chunk.search_text, 768)
        chunk.is_searchable = searchable
    Chunk.objects.bulk_create(chunks)
    return document


def candidate(**overrides):
    values = dict(
        chunk_id='c', document_id='d', chunk_index=0, content='text', heading_path='',
        page_start=None, page_end=None, title='T', url='', category='other',
        academic_year='', is_current=True, source_type='text', storage_path='',
    )
    values.update(overrides)
    return Candidate(**values)


class FusionTests(SimpleTestCase):
    def test_rrf_rewards_agreement(self):
        scores, ranks = fuse({'vector:0': ['a', 'b', 'c'], 'vector:1': ['b', 'd']})
        self.assertEqual(max(scores, key=scores.get), 'b')
        self.assertEqual(ranks['b'], {'vector:0': 2, 'vector:1': 1})


class RetrieveTests(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        self.llm = make_llm(self.fake)
        add_document('Hostel fee structure', ['Boys hostel fee is Rs 1,20,000 per year.'],
                     year='2026-27')
        add_document('Library timings', ['The central library opens at 8 am daily.'],
                     category='hostel_campus_life')
        add_document('Old hostel fees', ['Boys hostel fee was Rs 99,000 per year.'],
                     searchable=False)

    def test_relevant_chunk_ranks_first_and_hidden_chunks_never_appear(self):
        result = retrieve(self.llm, 'boys hostel fee')
        self.assertEqual(result.candidates[0].title, 'Hostel fee structure')
        self.assertNotIn('Old hostel fees', [c.title for c in result.candidates])
        self.assertEqual(set(result.lists), {'vector:0'})


class ContextTests(TestCase):
    def test_adjacent_chunks_share_one_number(self):
        document = add_document('Fee table', [
            '| Programme | Fee |\n|---|---|\n| COE | 2,25,000 |',
            '| Programme | Fee |\n|---|---|\n| ECE | 2,10,000 |',
        ])
        hits = [
            candidate(chunk_id=str(chunk.pk), document_id=str(document.pk),
                      chunk_index=chunk.chunk_index, content=chunk.content, title=document.title)
            for chunk in document.chunks.order_by('chunk_index')
        ]
        sources = build_sources(hits)
        self.assertEqual(len(sources), 1)
        self.assertIn('COE', sources[0].content)
        self.assertIn('ECE', sources[0].content)
        self.assertNotIn('storage_path', sources[0].public())

    def test_budget_limits_sources(self):
        items = [candidate(chunk_id=str(i), document_id=str(i), content='word ' * 800 + '.')
                 for i in range(5)]
        sources = build_sources(items, budget=2500)
        self.assertEqual([s.number for s in sources], [1, 2])


class CitationTests(SimpleTestCase):
    def test_numbers_in_order_of_first_use(self):
        self.assertEqual(cited_numbers('See [2] and [1, 2], not [12].', 3), [2, 1])


class PipelineTests(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        use_provider(self.fake)
        self.addCleanup(use_provider, None)
        add_document('Hostel fee structure', ['Boys hostel fee is Rs 1,20,000 per year.'])

    def test_answered_with_citation(self):
        self.fake.queue('The boys hostel fee is Rs 1,20,000 [1].')
        events = list(answer_events('boys hostel fee?'))
        names = [name for name, _ in events]
        self.assertEqual(names[:2], ['status', 'sources'])
        self.assertIn('delta', names)
        result = events[-1][1]
        self.assertEqual(result.answer_type, AnswerType.ANSWERED)
        self.assertEqual(result.cited, [1])

    def test_uncited_answer_is_no_answer(self):
        self.fake.queue("I couldn't find that in the documents.")
        result = answer('boys hostel fee?')
        self.assertEqual(result.answer_type, AnswerType.NO_ANSWER)

    def test_not_found_with_related_citation_is_no_answer(self):
        self.fake.queue('I couldn’t find the Wi-Fi password. Hostel IT desk: [1].')
        result = answer('wifi password?')
        self.assertEqual(result.answer_type, AnswerType.NO_ANSWER)

    def test_empty_knowledge_base_skips_generation(self):
        Document.objects.all().delete()
        result = answer('boys hostel fee?')
        self.assertEqual(result.text, NOT_FOUND)
        self.assertEqual(self.fake.requests, [])

    def test_history_is_passed_to_the_answer_model(self):
        self.fake.queue('Fee is Rs 1,20,000 [1].')
        answer('and boys?',
               history=[{'role': 'user', 'content': 'girls hostel fee?'},
                        {'role': 'assistant', 'content': 'x' * 5000}])
        final = self.fake.requests[-1]
        self.assertEqual(final.history[0].content, 'girls hostel fee?')
        self.assertLess(len(final.history[1].content), 1300)
        self.assertIn('<source n="1"', final.prompt)
