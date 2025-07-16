import hashlib
from datetime import date
from unittest import mock

from django.db import OperationalError, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from knowledge.ingest.chunk import ChunkDraft
from knowledge.ingest.pipeline import prepare_chunks
from knowledge.models import Chunk, Document, DocumentStatus, SourceType

from rag import evaluation, grounding
from rag.analysis import Intent, QueryAnalysis, _clean, analyze, current_session
from rag.context import build_sources
from rag.llm import BadResponse, use_provider
from rag.llm.client import LLM
from rag.llm.fake import FakeProvider, hashed_embedding
from rag.pipeline import NOT_FOUND, AnswerType, answer, answer_events
from rag.rerank import MIN_SCORE, rerank
from rag.retrieve import (
    BOOST,
    Candidate,
    KeywordSearch,
    _keyword_executor,
    _keyword_list_in_thread,
    apply_boosts,
    fuse,
    keyword_query,
    retrieve,
)


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


class AnalysisTests(SimpleTestCase):
    def test_clean_validates_model_output(self):
        analysis = _clean(
            {
                'intent': 'nonsense',
                'standalone_query': 'What is the fee?',
                'alternate_queries': ['a', 'b', 'c'],
                'keywords': 'fee',
                'categories': ['fees_scholarships', 'made_up'],
                'academic_year': '2026',
                'needs_current': True,
                'language': 'klingon',
            },
            'fee?',
        )
        self.assertEqual(analysis.intent, Intent.COLLEGE)
        self.assertEqual(analysis.alternate_queries, ['a', 'b'])
        self.assertEqual(analysis.categories, ['fees_scholarships'])
        self.assertEqual(analysis.academic_year, '')
        self.assertEqual(analysis.language, 'english')

    def test_search_queries_are_unique_and_capped(self):
        analysis = QueryAnalysis(
            question='q',
            standalone_query='Hostel fee',
            alternate_queries=['hostel fee', 'Mess fee'],
        )
        self.assertEqual(analysis.search_queries, ['Hostel fee', 'Mess fee'])

    def test_failure_falls_back_to_raw_question(self):
        fake = FakeProvider()
        fake.queue(BadResponse('nope'), BadResponse('nope again'))
        analysis = analyze(make_llm(fake), 'hostel fee?')
        self.assertTrue(analysis.fallback)
        self.assertEqual(analysis.search_queries, ['hostel fee?'])

    def test_prompt_contains_history_profile_and_session(self):
        fake = FakeProvider()
        fake.queue({'intent': 'college_query', 'standalone_query': 'x', 'alternate_queries': [],
                    'keywords': '', 'categories': [], 'academic_year': '',
                    'needs_current': False, 'language': 'english'})
        analyze(
            make_llm(fake), 'and for girls?',
            history=[{'role': 'user', 'content': 'boys hostel fee'}],
            profile={'program': 'BE COE', 'campus': ''},
            today=date(2026, 9, 25),
        )
        prompt = fake.requests[0].prompt
        self.assertIn('Student: boys hostel fee', prompt)
        self.assertIn('program: BE COE', prompt)
        self.assertIn('2026-27', prompt)
        self.assertEqual(fake.requests[0].model, 'fast')

    def test_current_session(self):
        self.assertEqual(current_session(date(2026, 9, 1)), '2026-27')
        self.assertEqual(current_session(date(2027, 3, 1)), '2026-27')
        self.assertEqual(current_session(date(2099, 12, 1)), '2099-00')


class FusionTests(SimpleTestCase):
    def test_rrf_rewards_agreement(self):
        scores, ranks = fuse({'vector:0': ['a', 'b', 'c'], 'keyword': ['b', 'd']})
        self.assertEqual(max(scores, key=scores.get), 'b')
        self.assertEqual(ranks['b'], {'vector:0': 2, 'keyword': 1})

    def test_boosts_are_bounded(self):
        strong = candidate(chunk_id='strong', category='other', is_current=False)
        weak = candidate(chunk_id='weak', category='fees_scholarships', academic_year='2026-27')
        strong.fused, weak.fused = 1 / 61, 1 / 90
        analysis = QueryAnalysis(question='q', categories=['fees_scholarships'],
                                 academic_year='2026-27', needs_current=True)
        apply_boosts([strong, weak], analysis)
        self.assertAlmostEqual(weak.boost, 3 * BOOST * strong.fused)
        self.assertLessEqual(weak.boost, 0.3 * strong.fused + 1e-12)

    def test_near_duplicates_keep_best_ranked_copy(self):
        from rag.retrieve import drop_near_duplicates

        text = 'Academic calendar odd semester 2026-27 first year classes begin 1 August'
        items = [
            candidate(chunk_id='a', content=text, url='https://one'),
            candidate(chunk_id='b', content='Hostel fee table'),
            candidate(chunk_id='c', content=text + '.', url='https://two'),
        ]
        self.assertEqual([c.chunk_id for c in drop_near_duplicates(items)], ['a', 'b'])

    def test_keyword_query_is_safe_or_query(self):
        self.assertEqual(keyword_query("UCS301 fee's & (drop) 2026-27"),
                         'ucs301 | fee | s | drop | 2026 | 27')
        self.assertEqual(keyword_query('!!!'), '')


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
        analysis = QueryAnalysis(question='boys hostel fee', standalone_query='boys hostel fee',
                                 keywords='hostel fee boys')
        result = retrieve(self.llm, analysis)
        self.assertEqual(result.candidates[0].title, 'Hostel fee structure')
        self.assertNotIn('Old hostel fees', [c.title for c in result.candidates])
        self.assertEqual(set(result.lists), {'vector:0', 'keyword'})

    def test_course_codes_found_by_keyword(self):
        add_document('CSE scheme', ['UCS301 Data Structures laboratory work.'],
                     category='courses_syllabus')
        analysis = QueryAnalysis(question='ucs301 lab', standalone_query='ucs301 lab',
                                 keywords='UCS301')
        result = retrieve(self.llm, analysis)
        self.assertEqual(result.lists['keyword'][0],
                         str(Chunk.objects.get(content__startswith='UCS301').pk))


class ParallelKeywordSearchTests(TransactionTestCase):
    """The keyword list runs on a pool thread with its own connection."""

    def tearDown(self):
        # The pool thread keeps its connection for the next search; close it so the test
        # database can be dropped. One search at a time uses a single pool thread.
        _keyword_executor.submit(connections.close_all).result()

    def test_same_lists_as_inline(self):
        add_document('Hostel fee structure', ['Boys hostel fee is Rs 1,20,000 per year.'])
        add_document('Library timings', ['The central library opens at 8 am daily.'])
        llm = make_llm(FakeProvider())
        analysis = QueryAnalysis(question='boys hostel fee', standalone_query='boys hostel fee',
                                 keywords='hostel fee boys')
        inline = retrieve(llm, analysis)
        with override_settings(RETRIEVE_PARALLEL=True):
            search = KeywordSearch(analysis)
            self.assertIsNotNone(search._future)
            parallel = retrieve(llm, analysis, keywords=search)
        self.assertEqual(parallel.lists, inline.lists)
        self.assertEqual([c.chunk_id for c in parallel.candidates],
                         [c.chunk_id for c in inline.candidates])

    def test_a_dropped_pool_connection_is_reopened(self):
        add_document('Hostel fee structure', ['Boys hostel fee is Rs 1,20,000 per year.'])
        calls = []

        def flaky(keywords, *, size=40):
            calls.append(keywords)
            if len(calls) == 1:
                raise OperationalError('server closed the connection unexpectedly')
            return ['chunk-id']

        with mock.patch('rag.retrieve.keyword_list', side_effect=flaky):
            self.assertEqual(_keyword_list_in_thread('hostel fee'), ['chunk-id'])
        self.assertEqual(len(calls), 2)


class RerankTests(SimpleTestCase):
    def test_orders_by_score_and_drops_irrelevant(self):
        fake = FakeProvider()
        fake.queue({'scores': [{'id': 0, 'score': 2}, {'id': 1, 'score': 9},
                               {'id': 2, 'score': 6}]})
        items = [candidate(chunk_id=str(i)) for i in range(3)]
        kept, reranked = rerank(make_llm(fake), 'q', items)
        self.assertTrue(reranked)
        # '0' scored low but is the top fused candidate, so it is kept (after the others).
        self.assertEqual([c.chunk_id for c in kept], ['1', '2', '0'])
        self.assertTrue(all(c.rerank_score >= MIN_SCORE for c in kept[:2]))

    def test_top_fused_candidate_is_dropped_only_at_zero(self):
        fake = FakeProvider()
        fake.queue({'scores': [{'id': 0, 'score': 0}, {'id': 1, 'score': 1},
                               {'id': 2, 'score': 7}]})
        items = [candidate(chunk_id=str(i)) for i in range(3)]
        kept, _ = rerank(make_llm(fake), 'q', items)
        self.assertEqual([c.chunk_id for c in kept], ['2', '1'])

    def test_failure_keeps_fused_order(self):
        fake = FakeProvider()
        fake.queue(BadResponse('x'))
        items = [candidate(chunk_id=str(i)) for i in range(10)]
        kept, reranked = rerank(make_llm(fake), 'q', items)
        self.assertFalse(reranked)
        self.assertEqual(len(kept), 8)


class ContextTests(TestCase):
    def test_split_table_is_rejoined_under_one_number(self):
        document = add_document('Fee table', [
            'Fee details for 2026-27 are below.',
            '| Programme | Fee |\n|---|---|\n| COE | 2,25,000 |',
            '| Programme | Fee |\n|---|---|\n| ECE | 2,10,000 |',
            'Unrelated closing notes.',
        ])
        chunks = list(document.chunks.order_by('chunk_index'))
        hit = candidate(chunk_id=str(chunks[1].pk), document_id=str(document.pk),
                        chunk_index=1, content=chunks[1].content, title=document.title)
        sources = build_sources([hit])
        self.assertEqual(len(sources), 1)
        self.assertIn('COE', sources[0].content)
        self.assertIn('ECE', sources[0].content)
        self.assertIn('Fee details', sources[0].content)
        self.assertNotIn('Unrelated', sources[0].content)
        self.assertNotIn('storage_path', sources[0].public())

    def test_budget_limits_sources(self):
        items = [candidate(chunk_id=str(i), document_id=str(i), content='word ' * 800 + '.')
                 for i in range(5)]
        sources = build_sources(items, budget=2500, expand=False)
        self.assertEqual([s.number for s in sources], [1, 2])


class GroundingTests(SimpleTestCase):
    def sources(self):
        return [
            candidate_source(1, 'Hostel fee is Rs 1,20,000 per year for 2026-27.'),
            candidate_source(2, 'Mess charges are 45000 per year.'),
        ]

    def test_supported_figures(self):
        check = grounding.check('The hostel fee is Rs 1,20,000 for 2026-27 [1].', self.sources())
        self.assertEqual(check.cited, [1])
        self.assertTrue(check.grounded)

    def test_calculated_total_is_flagged(self):
        check = grounding.check('Total is Rs 1,65,000 [1][2].', self.sources())
        self.assertEqual(check.cited, [1, 2])
        self.assertEqual(check.unsupported, ['165000'])

    def test_figure_from_uncited_source_is_flagged(self):
        check = grounding.check('Mess is 45000 [1].', self.sources())
        self.assertFalse(check.grounded)

    def test_academic_sessions_match_across_dash_styles(self):
        sources = [candidate_source(1, 'Document verification for the 2026�27 batch.')]
        for text in ('the 2026-27 batch [1]', 'the 2026–27 batch [1]', 'the 2026-2027 batch [1]'):
            with self.subTest(text=text):
                self.assertTrue(grounding.check(text, sources).grounded)
        self.assertFalse(grounding.check('the 2025-26 batch [1]', sources).grounded)

    def test_figures_from_source_title_count(self):
        source = candidate_source(1, 'Bring the anti-ragging affidavit.')
        source.title = 'Document verification - BE/BTech 2026-27 batch'
        self.assertTrue(grounding.check('For the 2026-27 batch [1].', [source]).grounded)

    def test_dates_match_across_formats(self):
        sources = [candidate_source(1, 'Last counselling round on 14th August, 2026.')]
        for text in ('Final round on August 14, 2026 [1].', 'Final round on 14 Aug 2026 [1].',
                     'Final round on 14.08.2026 [1].'):
            with self.subTest(text=text):
                self.assertTrue(grounding.check(text, sources).grounded)
        self.assertEqual(grounding.check('Final round on August 15, 2026 [1].',
                                         sources).unsupported, ['date:08-15'])

    def test_citation_numbers_are_not_figures(self):
        check = grounding.check('See [12] and [1, 2].', self.sources())
        self.assertEqual(check.cited, [1, 2])
        self.assertTrue(check.grounded)


def candidate_source(number, content):
    from rag.context import Source

    return Source(number=number, document_id='d', chunk_ids=[], title='t', url='',
                  heading_path='', page_start=None, page_end=None, academic_year='',
                  category='other', is_current=True, source_type='text', storage_path='',
                  content=content)


ANALYSIS = {'intent': 'college_query', 'standalone_query': 'boys hostel fee 2026-27',
            'alternate_queries': [], 'keywords': 'hostel fee', 'categories': [],
            'academic_year': '', 'needs_current': True, 'language': 'english'}


class PipelineTests(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        use_provider(self.fake)
        self.addCleanup(use_provider, None)
        add_document('Hostel fee structure', ['Boys hostel fee is Rs 1,20,000 per year.'])

    def test_greeting_uses_canned_reply_without_retrieval(self):
        self.fake.queue({**ANALYSIS, 'intent': 'greeting'})
        result = answer('hi')
        self.assertEqual(result.answer_type, AnswerType.SMALLTALK)
        self.assertEqual(len(self.fake.requests), 1)
        self.assertEqual(self.fake.embed_calls, [])

    def test_answered_with_citation(self):
        self.fake.queue(ANALYSIS, 'The boys hostel fee is Rs 1,20,000 [1].')
        events = list(answer_events('boys hostel fee?', rerank_enabled=False))
        names = [name for name, _ in events]
        self.assertEqual(names[:3], ['status', 'status', 'sources'])
        self.assertIn('delta', names)
        result = events[-1][1]
        self.assertEqual(result.answer_type, AnswerType.ANSWERED)
        self.assertTrue(result.grounded)
        self.assertEqual(result.cited, [1])
        self.assertEqual(result.analysis.standalone_query, 'boys hostel fee 2026-27')

    def test_uncited_answer_is_no_answer(self):
        self.fake.queue(ANALYSIS, "I couldn't find that in the documents.")
        result = answer('boys hostel fee?', rerank_enabled=False)
        self.assertEqual(result.answer_type, AnswerType.NO_ANSWER)
        self.assertIsNone(result.grounded)

    def test_not_found_with_related_citation_is_no_answer(self):
        self.fake.queue(ANALYSIS, 'I couldn’t find the Wi-Fi password. Hostel IT desk: [1].')
        result = answer('wifi password?', rerank_enabled=False)
        self.assertEqual(result.answer_type, AnswerType.NO_ANSWER)

    def test_nothing_relevant_after_rerank_skips_generation(self):
        add_document('Library', ['The library opens at 8 am.'], category='hostel_campus_life')
        self.fake.queue(ANALYSIS, {'scores': [{'id': 0, 'score': 0}, {'id': 1, 'score': 0}]})
        result = answer('boys hostel fee?', rerank_enabled=True)
        self.assertEqual(result.text, NOT_FOUND)
        self.assertEqual(result.answer_type, AnswerType.NO_ANSWER)

    def test_history_is_passed_to_the_answer_model(self):
        self.fake.queue(ANALYSIS, 'Fee is Rs 1,20,000 [1].')
        answer('and boys?', rerank_enabled=False,
               history=[{'role': 'user', 'content': 'girls hostel fee?'},
                        {'role': 'assistant', 'content': 'x' * 5000}])
        final = self.fake.requests[-1]
        self.assertEqual(final.history[0].content, 'girls hostel fee?')
        self.assertLess(len(final.history[1].content), 1300)
        self.assertIn('<source n="1"', final.prompt)


class EvaluationTests(SimpleTestCase):
    def test_hit_requires_url_and_phrases(self):
        expected = [{'url': 'https://a', 'contains': ['Dera Bassi']}]
        items = [candidate(url='https://a', content='Patiala hostel'),
                 candidate(url='https://a', content='dera bassi hostel')]
        self.assertEqual(evaluation.first_hit(items, expected), 2)

    def test_report_metrics(self):
        cases = [{'id': str(i), 'answerable': True, 'important': True} for i in range(4)]
        report = evaluation.Report([
            evaluation.CaseResult(case=cases[0], rank=1),
            evaluation.CaseResult(case=cases[1], rank=4),
            evaluation.CaseResult(case=cases[2], rank=8),
            evaluation.CaseResult(case=cases[3], rank=None),
        ])
        self.assertEqual(report.recall(5), 0.5)
        self.assertEqual(report.recall(10), 0.75)
        self.assertAlmostEqual(report.mrr(), (1 + 1 / 4 + 1 / 8) / 4)
        self.assertEqual(report.important_misses(), ['2', '3'])

    def test_golden_file_is_valid(self):
        cases = evaluation.load_cases()
        self.assertGreaterEqual(len(cases), 20)
        self.assertEqual(len({c['id'] for c in cases}), len(cases))
        for case in cases:
            self.assertEqual(bool(case['expected']), case['answerable'], case['id'])
