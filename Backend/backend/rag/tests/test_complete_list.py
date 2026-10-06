from django.test import SimpleTestCase, TestCase
from knowledge.models import Chunk

from rag import context
from rag.analysis import QueryAnalysis, _clean
from rag.context import LIST_BUDGET_TOKENS, build_sources, complete_list_candidates
from rag.llm import use_provider
from rag.llm.fake import FakeProvider
from rag.pipeline import answer
from rag.prompt import answer_prompt
from rag.retrieve import Candidate
from rag.tests.test_retrieval import ANALYSIS, add_document

HALLS = ['Agira', 'Amritam', 'Prithvi', 'Neeram', 'Vyan', 'Tejas', 'Ambaram', 'Viyat',
         'Anantam', 'Vyom']


def hall_chunks():
    """One hostel page: two chunks per hall, so a top-8 cut can never hold all ten."""
    chunks = []
    for hall in HALLS:
        chunks.append(f'{hall} Hall is a boys hostel on the main campus.')
        chunks.append(f'{hall} Hall has double rooms, a reading room and a common room.')
    return chunks


def candidates_for(document, chunk_indexes, *, other=None):
    rows = {c.chunk_index: c for c in Chunk.objects.filter(document=document)}
    found = [
        Candidate(chunk_id=str(rows[i].pk), document_id=str(document.pk), chunk_index=i,
                  content=rows[i].content, heading_path='', page_start=None, page_end=None,
                  title=document.title, url='', category='hostel_campus_life', academic_year='',
                  is_current=True, source_type='text', storage_path='', fused=1.0 - i / 100)
        for i in chunk_indexes
    ]
    return [*found, *(other or [])]


class CompleteListFlagTests(SimpleTestCase):
    def test_the_analysis_reads_the_flag_and_defaults_to_off(self):
        base = {'intent': 'college_query', 'standalone_query': 'q'}
        self.assertTrue(_clean({**base, 'wants_complete_list': True}, 'q').wants_complete_list)
        self.assertFalse(_clean(base, 'q').wants_complete_list)
        self.assertTrue(QueryAnalysis(question='q', wants_complete_list=True)
                        .as_dict()['wants_complete_list'])

    def test_the_prompt_asks_for_every_item_only_for_list_questions(self):
        plain = answer_prompt(QueryAnalysis(question='fee?'), [])
        listing = answer_prompt(QueryAnalysis(question='all hostels', wants_complete_list=True), [])
        self.assertNotIn('complete list', plain)
        self.assertIn('every item', listing)


class CompleteListCandidatesTests(TestCase):
    def setUp(self):
        self.document = add_document('Boys Hostel', hall_chunks(), category='hostel_campus_life')

    def test_most_chunks_from_one_page_pull_in_the_whole_page(self):
        top = candidates_for(self.document, [0, 4, 8, 10, 12, 16, 18])
        completed, expanded = complete_list_candidates(top)

        self.assertTrue(expanded)
        self.assertEqual([c.chunk_index for c in completed], list(range(20)))
        sources = build_sources(completed, budget=LIST_BUDGET_TOKENS)
        self.assertEqual(len(sources), 1)  # the page comes back whole under one citation
        for hall in HALLS:
            self.assertIn(hall, sources[0].content)

    def test_without_the_larger_budget_the_halls_are_cut_off(self):
        # What happens today: only the chunks that scored best are in the prompt.
        top = candidates_for(self.document, [0, 4, 8, 10, 12, 16, 18], other=[])
        text = ' '.join(s.content for s in build_sources(top, expand=False))
        self.assertNotIn('Amritam', text)

    def test_a_spread_of_documents_is_left_alone(self):
        other = add_document('Mess fee', ['Mess fee is Rs 5,000 per month.'])
        top = candidates_for(self.document, [0, 1], other=candidates_for(other, [0]))
        completed, expanded = complete_list_candidates(top)
        self.assertFalse(expanded)
        self.assertEqual(completed, top)

    def test_a_page_too_big_for_the_budget_adds_its_other_retrieved_chunks_instead(self):
        big = add_document('Huge page', ['word ' * 2000] * 8)  # about 20k tokens
        top = candidates_for(big, [0, 1, 2, 3])
        more = candidates_for(big, [4, 5])
        completed, expanded = complete_list_candidates(top, more)
        self.assertTrue(expanded)
        self.assertEqual([c.chunk_index for c in completed], [0, 1, 2, 3, 4, 5])

    def test_nothing_to_complete(self):
        self.assertEqual(complete_list_candidates([]), ([], False))

    def test_only_searchable_chunks_are_loaded(self):
        Chunk.objects.filter(document=self.document, chunk_index=19).update(is_searchable=False)
        top = candidates_for(self.document, [0, 4, 8])
        completed, _ = complete_list_candidates(top)
        self.assertNotIn(19, [c.chunk_index for c in completed])


class CompleteListPipelineTests(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        use_provider(self.fake)
        self.addCleanup(use_provider, None)
        add_document('Boys Hostel', hall_chunks(), category='hostel_campus_life')

    def test_a_list_question_sends_the_whole_page_to_the_model(self):
        self.fake.queue({**ANALYSIS, 'standalone_query': 'list all boys hostels',
                         'keywords': 'boys hostel halls', 'wants_complete_list': True},
                        'Agira, Amritam, Prithvi [1].')
        result = answer('list all boys hostels')
        prompt = self.fake.requests[-1].prompt
        for hall in HALLS:
            self.assertIn(hall, prompt)
        self.assertIn('every item', prompt)
        self.assertTrue(result.retrieval_trace['complete_list'])
        self.assertLessEqual(len(result.sources), 3)

    def test_an_ordinary_question_keeps_the_normal_budget(self):
        self.fake.queue({**ANALYSIS, 'standalone_query': 'boys hostel fee',
                         'keywords': 'boys hostel'}, 'Rs 5 [1].')
        result = answer('boys hostel fee?')
        self.assertFalse(result.retrieval_trace['complete_list'])
        self.assertNotIn('every item', self.fake.requests[-1].prompt)

    def test_budget_constants_leave_room_for_the_hostel_page(self):
        self.assertGreater(context.LIST_BUDGET_TOKENS, 7500)
        self.assertGreater(context.LIST_BUDGET_TOKENS, context.BUDGET_TOKENS)
