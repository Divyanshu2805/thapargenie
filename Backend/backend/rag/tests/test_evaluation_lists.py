from django.test import TestCase

from rag import evaluation
from rag.llm.fake import FakeProvider
from rag.tests.test_complete_list import HALLS, hall_chunks
from rag.tests.test_retrieval import ANALYSIS, add_document, make_llm


class EvaluationOfListsAndIntentsTests(TestCase):
    """The golden cases for "list all" and complaints (rag/eval/golden.json)."""

    def setUp(self):
        self.fake = FakeProvider()
        add_document('Boys Hostel', hall_chunks(), category='hostel_campus_life')
        self.case = {'id': 'list', 'question': 'list all boys hostels', 'expected': [],
                     'answerable': False, 'expect_type': 'answered', 'expect_all': HALLS}

    def evaluate(self, case, **analysis):
        self.fake.queue({**ANALYSIS, 'standalone_query': 'boys hostel halls list',
                         'keywords': 'boys hostel hall', **analysis})
        return evaluation.evaluate_case(make_llm(self.fake), case)

    def test_a_list_is_complete_only_when_every_item_reaches_the_prompt(self):
        self.assertTrue(self.evaluate(self.case, wants_complete_list=True).list_complete)
        # Without the fix every hall cannot fit: this is the failure the case guards against.
        self.assertFalse(self.evaluate(self.case, wants_complete_list=False).list_complete)

    def test_written_answers_must_name_every_item_too(self):
        analysis = {**ANALYSIS, 'standalone_query': 'boys hostel halls list',
                    'keywords': 'boys hostel hall', 'wants_complete_list': True}
        # The evaluator analyses the question, then the full pipeline does it again.
        self.fake.queue(analysis, analysis, 'Agira and Amritam [1].')
        result = evaluation.evaluate_case(make_llm(self.fake), self.case, with_answers=True)
        self.assertEqual(result.answer_type, 'answered')
        self.assertFalse(result.answer_complete)
        self.assertFalse(result.answer_ok)

    def test_intent_cases_check_the_question_type(self):
        complaint = {'id': 'c', 'question': 'why didnt you tell me before?', 'expected': [],
                     'answerable': False, 'expect_type': 'conversation',
                     'history': [{'role': 'user', 'content': 'boys hostels?'},
                                 {'role': 'assistant', 'content': 'Agira.'}]}
        self.assertTrue(self.evaluate(complaint, intent='conversation').intent_ok)
        self.assertFalse(self.evaluate(complaint, intent='greeting').intent_ok)

    def test_the_report_summarises_lists_and_intents(self):
        report = evaluation.Report([
            evaluation.CaseResult(case=self.case, list_complete=True),
            evaluation.CaseResult(case=self.case, list_complete=False),
            evaluation.CaseResult(case=self.case, intent_ok=True),
            evaluation.CaseResult(case=self.case),
        ])
        self.assertEqual(report.list_completeness(), 0.5)
        self.assertEqual(report.intent_accuracy(), 1.0)
        self.assertIsNone(evaluation.Report([]).list_completeness())

    def test_the_golden_file_holds_both_regression_cases(self):
        cases = {c['id']: c for c in evaluation.load_cases()}
        listing = cases['hostels-list-all-boys']
        self.assertEqual(listing['expect_all'], HALLS)
        complaint = cases['hostels-complaint-followup']
        self.assertEqual(complaint['expect_type'], 'conversation')
        self.assertEqual(complaint['history'][-1]['role'], 'assistant')
        for case in cases.values():
            if 'expect_all' in case:
                self.assertTrue(case['expect_all'])
                self.assertTrue(all(isinstance(item, str) and item for item in case['expect_all']))
