"""Measure retrieval (and optionally answer) quality against rag/eval/golden.json.

Retrieval metrics are computed on the fused candidate list (before reranking):
  recall@5 / recall@10  - share of answerable cases with a matching chunk in the top k
  MRR                   - mean reciprocal rank of the first matching chunk (top 25)
and on the final sources after reranking + context building:
  source hit            - a matching chunk made it into the answer prompt

With answers enabled it also checks the answer type (answered / no_answer / intents)
and whether answered cases passed the figure-grounding check.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from rag.analysis import Intent, analyze
from rag.context import sources_for
from rag.pipeline import AnswerType, answer
from rag.rerank import KEEP, rerank
from rag.retrieve import retrieve

GOLDEN = Path(__file__).parent / 'eval' / 'golden.json'


def load_cases(path=GOLDEN, only=None):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))['cases']
    return [case for case in cases if not only or case['id'] in only]


def _matches(item_url, item_text, expected):
    text = item_text.lower()
    for target in expected:
        if item_url == target['url'] and all(t.lower() in text for t in target['contains']):
            return True
    return False


def first_hit(candidates, expected):
    for rank, candidate in enumerate(candidates, start=1):
        if _matches(candidate.url, candidate.content, expected):
            return rank
    return None


@dataclass
class CaseResult:
    case: dict
    intent: str = ''
    standalone: str = ''
    rank: int | None = None
    source_hit: bool | None = None
    answer_type: str = ''
    grounded: bool | None = None
    answer_ok: bool | None = None
    # Cases that name items a complete answer must contain (`expect_all`): did every item
    # reach the answer prompt, and did the written answer name every one?
    list_complete: bool | None = None
    answer_complete: bool | None = None
    intent_ok: bool | None = None
    error: str = ''

    @property
    def answerable(self):
        return self.case['answerable']


@dataclass
class Report:
    results: list = field(default_factory=list)

    def _answerable(self):
        return [r for r in self.results if r.answerable and not r.error]

    def recall(self, k):
        rows = self._answerable()
        return sum(1 for r in rows if r.rank and r.rank <= k) / len(rows) if rows else 0.0

    def mrr(self):
        rows = self._answerable()
        return sum(1 / r.rank for r in rows if r.rank) / len(rows) if rows else 0.0

    def source_hit_rate(self):
        rows = [r for r in self._answerable() if r.source_hit is not None]
        return sum(1 for r in rows if r.source_hit) / len(rows) if rows else None

    def answer_accuracy(self):
        rows = [r for r in self.results if r.answer_ok is not None]
        return sum(1 for r in rows if r.answer_ok) / len(rows) if rows else None

    def list_completeness(self):
        rows = [r for r in self.results if r.list_complete is not None]
        return sum(1 for r in rows if r.list_complete) / len(rows) if rows else None

    def intent_accuracy(self):
        rows = [r for r in self.results if r.intent_ok is not None]
        return sum(1 for r in rows if r.intent_ok) / len(rows) if rows else None

    def important_misses(self):
        return [
            r.case['id']
            for r in self.results
            if r.case.get('important') and r.answerable and not (r.rank and r.rank <= 5)
        ]


def expected_type(case):
    if case.get('expect_type'):
        return case['expect_type']
    return AnswerType.ANSWERED if case['answerable'] else AnswerType.NO_ANSWER


# The question type the analysis should give for cases that expect a non-search reply.
INTENT_FOR_TYPE = {
    AnswerType.SMALLTALK: Intent.GREETING,
    AnswerType.CONVERSATION: Intent.CONVERSATION,
    AnswerType.OUT_OF_SCOPE: Intent.OUT_OF_SCOPE,
    AnswerType.PERSONAL_RECORD: Intent.PERSONAL_RECORD,
}


def names_all(text, items):
    text = text.lower()
    return all(item.lower() in text for item in items)


def evaluate_case(llm, case, *, use_rerank=False, with_answers=False):
    result = CaseResult(case=case)
    history = case.get('history', [])
    analysis = analyze(llm, case['question'], history=history)
    result.intent = analysis.intent
    result.standalone = analysis.standalone_query
    expected_intent = INTENT_FOR_TYPE.get(case.get('expect_type'))
    if expected_intent:
        result.intent_ok = analysis.intent == expected_intent
    if analysis.intent == Intent.COLLEGE and (case['expected'] or case.get('expect_all')):
        retrieval = retrieve(llm, analysis)
        kept = retrieval.candidates[:KEEP]
        if use_rerank:
            kept, _ = rerank(llm, analysis.standalone_query, retrieval.candidates)
        sources, _ = sources_for(analysis, kept, retrieval.candidates[KEEP:])
        if case['expected']:
            result.rank = first_hit(retrieval.candidates, case['expected'])
            result.source_hit = any(_matches(s.url, s.content, case['expected']) for s in sources)
        if case.get('expect_all'):
            result.list_complete = names_all(' '.join(s.content for s in sources),
                                             case['expect_all'])
    if with_answers:
        final = answer(case['question'], llm=llm, history=history, rerank_enabled=use_rerank)
        result.answer_type = final.answer_type
        result.grounded = final.grounded
        result.answer_ok = final.answer_type == expected_type(case)
        if case.get('expect_all'):
            result.answer_complete = names_all(final.text, case['expect_all'])
            result.answer_ok = result.answer_ok and result.answer_complete
    return result


def run(llm, cases, *, use_rerank=False, with_answers=False, on_result=None):
    report = Report()
    for case in cases:
        try:
            result = evaluate_case(llm, case, use_rerank=use_rerank, with_answers=with_answers)
        except Exception as exc:  # one broken case must not hide the rest of the report
            result = CaseResult(case=case, error=f'{type(exc).__name__}: {exc}')
        report.results.append(result)
        if on_result:
            on_result(result)
    return report
