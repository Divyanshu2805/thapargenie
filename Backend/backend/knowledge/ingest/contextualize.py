"""Contextual retrieval: one sentence per chunk saying where it sits in its document.

A chunk like "| Hall A | 1,20,000 |" is hard to find on its own. Prefixing it with
"Hostel fee table for 2026-27 first-year boys' hostels" fixes that. The sentence is
added to `search_text` only; the LLM always answers from the original chunk content.
"""

import logging

from rag.llm import BadResponse, LLMError, QuotaExhausted

logger = logging.getLogger(__name__)

BATCH = 10
# The model reads the document to place each chunk, so a long page must fit: the Boys Hostel
# page is ~30,000 characters, and with a shorter excerpt the later halls were never seen.
DOCUMENT_EXCERPT_CHARS = 60_000
# A document longer than that is read in windows: its opening, then the chunks around the
# ones being described.
OPENING_CHARS = 6_000

SCHEMA = {
    'type': 'object',
    'properties': {
        'contexts': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'index': {'type': 'integer'},
                    'context': {'type': 'string'},
                },
                'required': ['index', 'context'],
                'additionalProperties': False,
            },
        }
    },
    'required': ['contexts'],
    'additionalProperties': False,
}

PROMPT = """<document title="{title}">
{excerpt}
</document>

Below are numbered chunks from this document. For each chunk, write one short sentence \
(max 35 words) that situates it within the document, to improve search retrieval: say what \
the chunk is about and include the programme, year, hostel, section or other specifics it \
belongs to when the document makes that clear. Do not add facts that are not in the \
document. Do not repeat the chunk.

{chunks}

Return JSON: {{"contexts": [{{"index": <chunk number>, "context": "<sentence>"}}]}}"""


def _excerpt(document_text, contents, start, size):
    """What the model reads to place chunks `start` to `start + size`."""
    if len(document_text) <= DOCUMENT_EXCERPT_CHARS:
        return document_text
    low, high = start, min(start + size, len(contents))
    room = DOCUMENT_EXCERPT_CHARS - OPENING_CHARS - sum(len(c) for c in contents[low:high])
    while low > 0 or high < len(contents):
        grown = False
        if low > 0 and len(contents[low - 1]) <= room:
            low -= 1
            room -= len(contents[low])
            grown = True
        if high < len(contents) and len(contents[high]) <= room:
            room -= len(contents[high])
            high += 1
            grown = True
        if not grown:
            break
    return '\n\n'.join([document_text[:OPENING_CHARS], '[...]', *contents[low:high]])


def contextualize(llm, *, title, document_text, contents, strict=False):
    """Return one context sentence per chunk content ('' where none was produced).

    A failed batch leaves its chunks without context. With `strict` a used-up quota is raised
    instead, so a bulk run stops and can be resumed rather than silently skipping documents.
    """
    results = [''] * len(contents)
    for start in range(0, len(contents), BATCH):
        batch = contents[start : start + BATCH]
        numbered = '\n\n'.join(
            f'<chunk number="{start + offset}">\n{content[:3000]}\n</chunk>'
            for offset, content in enumerate(batch)
        )
        excerpt = _excerpt(document_text, contents, start, len(batch))
        prompt = PROMPT.format(title=title, excerpt=excerpt, chunks=numbered)
        try:
            data = llm.generate_json(
                prompt, json_schema=SCHEMA, fast=True, temperature=0, max_output_tokens=2048
            )
        except QuotaExhausted:
            if strict:
                raise
            logger.warning('Contextualisation skipped for %r: quota used up', title)
            continue
        except (BadResponse, LLMError) as error:
            # Context is an enhancement; a failed batch must not fail the document.
            logger.warning('Contextualisation failed for %r: %s', title, error)
            continue
        for item in data.get('contexts', []):
            index = item.get('index')
            if isinstance(index, int) and start <= index < start + len(batch):
                results[index] = ' '.join(str(item.get('context', '')).split())[:400]
    return results
