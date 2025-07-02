"""Listwise reranking with the fast model.

Fusion finds candidates; the reranker reads them against the question and scores
relevance 0-10. Low scorers are dropped so the answer model sees fewer, better sources.
If reranking fails, the fused order is used unchanged.
"""

import logging

from common.text import truncate

from rag.llm import BadResponse, LLMError

logger = logging.getLogger(__name__)

KEEP = 8
# Passages sent to the reranker. Fused recall@10 is 1.00 on the eval set, so 15 leaves
# headroom while keeping the rerank prompt (and its latency) small.
CANDIDATES = 15
MIN_SCORE = 3
# The reranker is a small fast model and its scores vary run to run (the same passage has
# scored 3, 6 and 8). It may reorder freely, but the best fused candidates are only
# dropped when it scores them 0; otherwise the answer model decides relevance.
PROTECTED_TOP = 2
PREVIEW_CHARS = 500

SCHEMA = {
    'type': 'object',
    'properties': {
        'scores': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'id': {'type': 'integer'}, 'score': {'type': 'integer'}},
                'required': ['id', 'score'],
                'additionalProperties': False,
            },
        }
    },
    'required': ['scores'],
    'additionalProperties': False,
}

PROMPT = """Question from a Thapar Institute (TIET) student:
<question>{question}</question>

Rate how useful each passage is for answering the question, from 0 (irrelevant) to 10 \
(directly answers it). Prefer passages for the right programme, campus and academic year. \
A fee or cutoff table for the wrong year scores at most 4. Judge only relevance.

{passages}

Return JSON: {{"scores": [{{"id": <passage id>, "score": <0-10>}}, ...]}} covering every \
passage."""


def _passage(index, candidate):
    meta = ' | '.join(
        part for part in (candidate.title, candidate.heading_path, candidate.academic_year) if part
    )
    body = truncate(candidate.content, PREVIEW_CHARS)
    return f'<passage id="{index}">\n[{meta}]\n{body}\n</passage>'


def rerank(llm, question, candidates, *, keep=KEEP):
    """Returns (kept candidates, reranked: bool)."""
    candidates = candidates[:CANDIDATES]
    if len(candidates) <= 1:
        return candidates, False
    passages = '\n\n'.join(_passage(i, c) for i, c in enumerate(candidates))
    try:
        data = llm.generate_json(
            PROMPT.format(question=question, passages=passages),
            json_schema=SCHEMA,
            fast=True,
            temperature=0,
            max_output_tokens=1024,
        )
    except (LLMError, BadResponse) as error:
        logger.warning('Rerank failed, keeping fused order: %s', error)
        return candidates[:keep], False
    scores = {}
    for item in data.get('scores', []):
        index, score = item.get('id'), item.get('score')
        if isinstance(index, int) and 0 <= index < len(candidates) and isinstance(score, int):
            scores[index] = max(0, min(10, score))
    for index, candidate in enumerate(candidates):
        candidate.rerank_score = scores.get(index, 0)
    ordered = sorted(
        range(len(candidates)), key=lambda i: (-candidates[i].rerank_score, i)
    )
    relevant = [candidates[i] for i in ordered if candidates[i].rerank_score >= MIN_SCORE]
    relevant = relevant[:keep]
    for candidate in candidates[:PROTECTED_TOP]:
        if candidate not in relevant and candidate.rerank_score > 0 and len(relevant) < keep:
            relevant.append(candidate)
    return relevant, True
