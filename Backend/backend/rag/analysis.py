"""Understand the question before searching.

One fast-model call turns a raw message (possibly a follow-up, possibly Hinglish) into
a standalone English search query, a few alternative phrasings, keywords for full-text
search and soft hints (category, academic year, whether current data matters).

If the call fails, retrieval still runs on the raw question: analysis improves results
but must never block an answer.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from knowledge.models import Category

from rag.llm import BadResponse, LLMError

logger = logging.getLogger(__name__)


class Intent:
    COLLEGE = 'college_query'
    GREETING = 'greeting'
    OUT_OF_SCOPE = 'out_of_scope'
    PERSONAL_RECORD = 'personal_record'
    ALL = (COLLEGE, GREETING, OUT_OF_SCOPE, PERSONAL_RECORD)


SCHEMA = {
    'type': 'object',
    'properties': {
        'intent': {'type': 'string', 'enum': list(Intent.ALL)},
        'standalone_query': {'type': 'string'},
        'alternate_queries': {'type': 'array', 'items': {'type': 'string'}},
        'keywords': {'type': 'string'},
        'categories': {'type': 'array', 'items': {'type': 'string', 'enum': Category.values}},
        'academic_year': {'type': 'string'},
        'needs_current': {'type': 'boolean'},
        'language': {'type': 'string', 'enum': ['english', 'hinglish', 'other']},
    },
    'required': [
        'intent',
        'standalone_query',
        'alternate_queries',
        'keywords',
        'categories',
        'academic_year',
        'needs_current',
        'language',
    ],
    'additionalProperties': False,
}

SYSTEM = """You prepare search queries for ThaparGenie, the student help assistant of Thapar \
Institute of Engineering and Technology (TIET), Patiala, India. You never answer the question.

Classify the latest user message:
- college_query: anything about TIET: admissions, fees, scholarships, hostels, mess, \
academic calendar, exams, courses, syllabus, rules, departments, faculty, placements, notices, \
campus facilities, contacts. When unsure, choose this.
- greeting: greetings, thanks, small talk, "what can you do".
- personal_record: the user's own marks, attendance, fee dues, results or login problems \
(these live in the Webkiosk portal, not in public documents).
- out_of_scope: clearly unrelated to TIET (general coding help, homework, news, other \
colleges, entertainment).

For college_query:
- standalone_query: rewrite the message as one complete English question that makes sense \
without the conversation. Resolve pronouns and follow-ups from the history ("and for girls?" \
-> "What is the girls hostel fee at TIET for 2026-27?"). Translate Hinglish to English. Expand \
abbreviations when clear (COE = Computer Engineering, sem = semester). Do not add the \
institute's name: every document is about TIET.
- alternate_queries: 0-2 different phrasings or sub-questions that would find other relevant \
documents. For comparisons, one query per item. Empty if not useful.
- keywords: 3-12 important search terms (codes like UCS301, programme names, hostel names, \
years, document names), space separated.
- categories: 1-2 most likely categories, or [] if unsure.
- academic_year: "YYYY-YY" if the question implies one (use the current session for "this \
year"), else "".
- needs_current: true for fees, deadlines, dates, cutoffs, admissions status, schedules.
For other intents, set standalone_query to the message and leave the rest empty/false.
language: the language style of the user's message."""

PROMPT = """Today is {today}. The current academic session is {session}.
{profile}
Conversation so far (oldest first):
{history}

Latest user message:
<message>{question}</message>"""

_YEAR = re.compile(r'^\d{4}-\d{2}$')


@dataclass
class QueryAnalysis:
    question: str
    intent: str = Intent.COLLEGE
    standalone_query: str = ''
    alternate_queries: list[str] = field(default_factory=list)
    keywords: str = ''
    categories: list[str] = field(default_factory=list)
    academic_year: str = ''
    needs_current: bool = False
    language: str = 'english'
    fallback: bool = False

    @property
    def search_queries(self):
        queries = [self.standalone_query or self.question, *self.alternate_queries]
        seen, unique = set(), []
        for query in queries:
            key = query.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(query.strip())
        return unique[:3]

    def as_dict(self):
        return {
            'intent': self.intent,
            'standalone_query': self.standalone_query,
            'alternate_queries': self.alternate_queries,
            'keywords': self.keywords,
            'categories': self.categories,
            'academic_year': self.academic_year,
            'needs_current': self.needs_current,
            'language': self.language,
            'fallback': self.fallback,
        }


def current_session(today):
    start = today.year if today.month >= 7 else today.year - 1
    return f'{start}-{(start + 1) % 100:02d}'


def _format_history(history, limit=6, max_chars=800):
    lines = []
    for message in list(history)[-limit:]:
        role = 'Student' if message['role'] == 'user' else 'Assistant'
        text = ' '.join(message['content'].split())
        lines.append(f'{role}: {text[:max_chars]}')
    return '\n'.join(lines) or '(none)'


def _format_profile(profile):
    if not profile:
        return ''
    parts = [f'{key}: {value}' for key, value in profile.items() if value]
    return f'Student profile (use only if the question depends on it): {", ".join(parts)}\n' \
        if parts else ''


def _clean(data, question):
    intent = data.get('intent') if data.get('intent') in Intent.ALL else Intent.COLLEGE
    year = str(data.get('academic_year') or '').strip()
    return QueryAnalysis(
        question=question,
        intent=intent,
        standalone_query=str(data.get('standalone_query') or question).strip()[:500],
        alternate_queries=[
            str(q).strip()[:300]
            for q in (data.get('alternate_queries') or [])[:2]
            if str(q).strip()
        ],
        keywords=str(data.get('keywords') or '').strip()[:300],
        categories=[c for c in (data.get('categories') or []) if c in Category.values][:2],
        academic_year=year if _YEAR.match(year) else '',
        needs_current=bool(data.get('needs_current')),
        language=data.get('language') if data.get('language') in
        ('english', 'hinglish', 'other') else 'english',
    )


def analyze(llm, question, *, history=(), profile=None, today=None):
    today = today or date.today()
    prompt = PROMPT.format(
        today=today.isoformat(),
        session=current_session(today),
        profile=_format_profile(profile),
        history=_format_history(history),
        question=question,
    )
    try:
        data = llm.generate_json(
            prompt,
            system=SYSTEM,
            json_schema=SCHEMA,
            fast=True,
            temperature=0,
            max_output_tokens=1024,
        )
    except (LLMError, BadResponse) as error:
        logger.warning('Query analysis failed, using the raw question: %s', error)
        return QueryAnalysis(question=question, standalone_query=question, keywords=question,
                             fallback=True)
    return _clean(data, question)
