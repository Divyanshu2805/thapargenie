"""Thapar-specific vocabulary: abbreviations and synonyms students and documents use.

Used to widen full-text search only (chunk `search_text` at ingestion, keyword
queries at retrieval). Embeddings get the original text: the model already knows
most synonyms, and appending lists of expansions would blur the vectors.

Each group lists equivalent spellings; any match adds the whole group.
"""

import re

GROUPS = [
    # Campuses and schools. The institute's own name is deliberately absent: every document
    # is about TIET, so it carries no search signal.
    ['Patiala campus', 'main campus'],
    ['Dera Bassi', 'Derabassi', 'TIET Dera Bassi'],
    ['TSLAS', 'Thapar School of Liberal Arts and Sciences'],
    ['LMTSM', 'Thapar School of Management', 'LM Thapar School of Management'],
    # Programmes
    ['COE', 'BE COE', 'Computer Engineering'],
    ['CSE', 'Computer Science and Engineering', 'Computer Science'],
    ['CSBS', 'Computer Science and Business Systems'],
    ['ENC', 'Electronics and Computer Engineering'],
    ['ECE', 'Electronics and Communication Engineering'],
    ['EIC', 'Electronics Instrumentation and Control'],
    ['EE', 'Electrical Engineering'],
    ['ME', 'Mechanical Engineering'],
    ['CE', 'Civil Engineering'],
    ['CHE', 'Chemical Engineering'],
    ['BT', 'Biotechnology'],
    ['AI&DS', 'AIDS', 'AI DS', 'Artificial Intelligence and Data Science'],
    ['RAI', 'Robotics and Artificial Intelligence'],
    ['BE', 'B.E.', 'Bachelor of Engineering', 'BTech', 'B.Tech', 'Bachelor of Technology'],
    ['ME', 'M.E.', 'Master of Engineering', 'MTech', 'M.Tech'],
    ['MCA', 'Master of Computer Applications'],
    ['MBA', 'Master of Business Administration'],
    ['PhD', 'Ph.D.', 'doctorate', 'doctoral'],
    # Academics
    ['sem', 'semester'],
    ['CGPA', 'cumulative grade point average'],
    ['SGPA', 'semester grade point average'],
    ['MST', 'mid semester test', 'mid-semester test', 'mid sem', 'midsem'],
    ['EST', 'end semester test', 'end-semester test', 'end sem', 'endsem'],
    ['timetable', 'time table', 'schedule'],
    ['syllabus', 'course content', 'scheme'],
    ['elective', 'electives', 'ELE'],
    # Admissions and money
    ['JEE', 'JEE Main', 'JEE Mains'],
    ['cutoff', 'cut off', 'closing rank', 'closing ranks'],
    ['fee', 'fees', 'fee structure', 'tuition'],
    ['refund', 'fee refund', 'withdrawal'],
    ['scholarship', 'scholarships', 'financial aid', 'merit scholarship'],
    ['NSP', 'National Scholarship Portal'],
    # Campus life
    ['hostel', 'hostels', 'hall', 'halls of residence'],
    ['boys hostel', "boys' hostel", 'mens hostel', "men's hostel"],
    ['girls hostel', "girls' hostel", 'womens hostel', "women's hostel", 'ladies hostel'],
    ['mess', 'dining', 'mess fee'],
    ['anti-ragging', 'anti ragging', 'ragging'],
    ['TPO', 'placement cell', 'training and placement'],
    ['CR', 'class representative'],
    ['DOSA', 'Dean of Student Affairs'],
    ['webkiosk', 'web kiosk'],
]

_ROMAN = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8,
}
_ORDINAL = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th', 6: '6th', 7: '7th', 8: '8th'}
_WORD = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth',
         7: 'seventh', 8: 'eighth'}


def _pattern(term):
    return re.compile(r'(?<![\w&])' + re.escape(term) + r'(?![\w&])', re.IGNORECASE)


_COMPILED = [[(_pattern(term), term) for term in group] for group in GROUPS]

_SEMESTER = re.compile(
    r'\b(?:(?P<roman>VIII|VII|VI|IV|V|III|II|I)|(?P<num>[1-8])(?:st|nd|rd|th)?'
    r'|(?P<word>first|second|third|fourth|fifth|sixth|seventh|eighth))'
    r'\s*(?:sem|semester)\b'
    r'|\bsem(?:ester)?\s*[-:]?\s*(?P<roman2>VIII|VII|VI|IV|V|III|II|I|[1-8])\b',
    re.IGNORECASE,
)


def _semester_terms(text):
    terms = set()
    for match in _SEMESTER.finditer(text):
        value = match.group('roman') or match.group('roman2') or match.group('num') or ''
        word = (match.group('word') or '').lower()
        if word:
            number = next(n for n, w in _WORD.items() if w == word)
        elif value.isdigit():
            number = int(value)
        else:
            number = _ROMAN.get(value.upper())
        if not number:
            continue
        roman = next(r for r, n in _ROMAN.items() if n == number)
        terms.update({
            f'semester {roman}',
            f'semester {number}',
            f'{_ORDINAL[number]} semester',
            f'{_WORD[number]} semester',
        })
    return terms


def expansions(text):
    """Synonyms for terms present in `text` that are not already in it."""
    found = set()
    for group in _COMPILED:
        if any(pattern.search(text) for pattern, _ in group):
            found.update(term for pattern, term in group if not pattern.search(text))
    found.update(term for term in _semester_terms(text) if term.lower() not in text.lower())
    return sorted(found, key=str.lower)


def expand(text):
    """`text` followed by a line of extra search terms (or unchanged)."""
    extra = expansions(text)
    return f'{text}\n\n{"; ".join(extra)}' if extra else text
