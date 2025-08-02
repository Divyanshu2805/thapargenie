"""Suggest a missing session (academic year) and issue date for documents.

Nothing here writes: an admin reviews the suggestions and applies them through the bulk
endpoint. Rules come first and are free; the AI is used only when the admin asks, only
for documents the rules left empty, and only a few at a time.
"""

import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date

from chat import quota
from chat.errors import ServiceBusy
from chat.models import ChatSettings
from common.text import truncate
from rag.llm import BadResponse, LLMError, get_llm

from knowledge.models import Category, Chunk

logger = logging.getLogger(__name__)

# Categories whose content changes by session or date; others (faculty, departments,
# about pages) don't need one.
TIME_SENSITIVE = (
    Category.FEES_SCHOLARSHIPS,
    Category.ADMISSIONS,
    Category.ACADEMIC_CALENDAR,
    Category.NOTICES,
    Category.PLACEMENTS,
)
MAX_AI_DOCUMENTS = 20
TEXT_PASSAGES = 3
AI_TEXT_CHARS = 3000

# "2026-27", "2026-2027", "2026–27", "2026/27": only consecutive years are sessions.
# Digit boundaries, not \b: file-style titles run on ("…EVEN 2025-26_PhD-1").
_SESSION = re.compile(r'(?<!\d)(20\d{2})\s*[-–/]\s*(?:20)?(\d{2})(?!\d)')
# Table borders and broken characters from extracted PDFs, dropped from evidence.
_NOISE = re.compile(r'[|�]+')
_SESSION_FORMAT = re.compile(r'^\d{4}-\d{2}$')


@dataclass
class Suggestion:
    id: str
    title: str
    current_academic_year: str
    current_effective_date: str | None
    academic_year: str = ''
    effective_date: str | None = None
    source: str = ''  # 'title' | 'text' | 'ai' | '' (nothing found)
    evidence: str = ''

    def as_dict(self):
        return asdict(self)


def sessions_in(text):
    """[(session, matched text)] in order of appearance."""
    found = []
    for match in _SESSION.finditer(text or ''):
        start, end = match.groups()
        if int(end) == (int(start) + 1) % 100:
            found.append((f'{start}-{end}', match.group(0)))
    return found


def _excerpt(text, phrase, width=60):
    at = text.find(phrase)
    if at < 0:
        return phrase
    start, end = max(0, at - width), min(len(text), at + len(phrase) + width)
    excerpt = ' '.join(_NOISE.sub(' ', text[start:end]).split())
    return ('…' if start else '') + excerpt + ('…' if end < len(text) else '')


def suggest_from_rules(document, passages):
    """A session from the title or file name, else the single (or clearly most frequent)
    session in the first passages."""
    suggestion = Suggestion(
        id=str(document.pk), title=document.title,
        current_academic_year=document.academic_year,
        current_effective_date=(document.effective_date.isoformat()
                                if document.effective_date else None),
    )
    for field in (document.title, document.original_filename):
        found = sessions_in(field)
        if found:
            suggestion.academic_year, phrase = found[0]
            suggestion.source, suggestion.evidence = 'title', _excerpt(field, phrase)
            return suggestion
    text = '\n'.join(passages)
    found = sessions_in(text)
    if not found:
        return suggestion
    counts = Counter(session for session, _ in found).most_common(2)
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        suggestion.evidence = 'Several sessions are mentioned: ' + ', '.join(
            sorted({session for session, _ in found}))
        return suggestion
    best = counts[0][0]
    phrase = next(p for session, p in found if session == best)
    suggestion.academic_year, suggestion.source = best, 'text'
    suggestion.evidence = _excerpt(text, phrase)
    return suggestion


AI_SCHEMA = {
    'type': 'object',
    'properties': {
        'academic_year': {'type': 'string'},
        'effective_date': {'type': 'string'},
        'quote': {'type': 'string'},
    },
    'required': ['academic_year', 'effective_date', 'quote'],
}

AI_PROMPT = """Below is the start of an official document of Thapar Institute (TIET), India.
Say which academic session it applies to and the date it was issued, but only if the text \
states them. Do not guess.

- academic_year: "YYYY-YY" (e.g. "2026-27") if the document names the session it applies \
to, else "".
- effective_date: "YYYY-MM-DD" if the document states when it was issued or dated (not a \
deadline or an event date), else "".
- quote: the exact short phrase (under 100 characters) the answer is based on, else "".

Today is {today}.

Title: {title}

Text:
{text}"""


def _clean_ai(data, today):
    year = str(data.get('academic_year') or '').strip()
    if not _SESSION_FORMAT.match(year) or int(year[5:]) != (int(year[:4]) + 1) % 100:
        year = ''
    issued = None
    try:
        value = date.fromisoformat(str(data.get('effective_date') or '').strip())
        issued = value.isoformat() if value <= today else None
    except ValueError:
        pass
    return year, issued, truncate(' '.join(str(data.get('quote') or '').split()), 150)


def suggest(documents, *, user, ai=False, today=None):
    """Suggestions for `documents` (in order). With `ai`, the fast model is asked about
    the first MAX_AI_DOCUMENTS that the rules left without a session."""
    today = today or date.today()
    passages = {}
    for chunk in (Chunk.objects.filter(document__in=documents, chunk_index__lt=TEXT_PASSAGES)
                  .order_by('document_id', 'chunk_index').values('document_id', 'content')):
        passages.setdefault(chunk['document_id'], []).append(chunk['content'])
    results = [suggest_from_rules(document, passages.get(document.pk, []))
               for document in documents]
    if not ai:
        return [result.as_dict() for result in results]

    pending = [(document, result) for document, result in zip(documents, results, strict=True)
               if not result.academic_year][:MAX_AI_DOCUMENTS]
    if pending:
        settings = ChatSettings.load()
        if quota.global_calls_today() >= settings.global_daily_llm_calls:
            raise ServiceBusy()
        llm = get_llm()
        try:
            for document, result in pending:
                text = truncate('\n'.join(passages.get(document.pk, [])), AI_TEXT_CHARS)
                try:
                    data = llm.generate_json(
                        AI_PROMPT.format(today=today.isoformat(), title=document.title,
                                         text=text or '(no text)'),
                        json_schema=AI_SCHEMA, fast=True, temperature=0, max_output_tokens=200,
                    )
                except (LLMError, BadResponse) as error:
                    logger.warning('AI details suggestion failed for %s: %s', document.pk, error)
                    continue
                year, issued, quote = _clean_ai(data if isinstance(data, dict) else {}, today)
                if year or issued:
                    result.academic_year, result.effective_date = year, issued
                    result.source, result.evidence = 'ai', quote
        finally:
            quota.record_calls(user, llm.usage)
    return [result.as_dict() for result in results]
