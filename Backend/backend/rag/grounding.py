"""Cheap, deterministic checks on a finished answer (no extra LLM call).

- Which sources were actually cited ([n] markers).
- Whether every figure in the answer (amounts, years, dates, ranks) appears in the text of
  the sources it cites. Fees and cutoffs are where a wrong answer hurts students most, and
  a figure that is not in the cited text is either a hallucination or a calculation.
"""

import re
from dataclasses import dataclass, field

_CITATION = re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]')
_SESSION = re.compile(r'\b(20\d{2})\s*[-–—/�]\s*((?:20)?\d{2})\b')
# 2+ digit numbers, with Indian/Western separators and decimals: 1,20,000 | 53883 | 7.5
_FIGURE = re.compile(
    r'(?<![\w.])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?(?![\w])'  # grouped: 1,20,000 / 120,000.50
    r'|(?<![\w.,])\d{2,}(?:\.\d+)?(?![\w])'  # plain: 53883 / 2026 / 7.5
)

_MONTHS = {
    name: number
    for number, names in enumerate(
        [('jan', 'january'), ('feb', 'february'), ('mar', 'march'), ('apr', 'april'),
         ('may',), ('jun', 'june'), ('jul', 'july'), ('aug', 'august'),
         ('sep', 'sept', 'september'), ('oct', 'october'), ('nov', 'november'),
         ('dec', 'december')],
        start=1,
    )
    for name in names
}
_MONTH = r'(?P<month>' + '|'.join(sorted(_MONTHS, key=len, reverse=True)) + r')\.?'
_DAY = r'(?P<day>\d{1,2})(?:st|nd|rd|th)?'
# Only the day+month part (group 'dm') is replaced by a token; a following year stays a
# normal figure, so "14 August 2026" yields date:08-14 and 2026.
_DATE_PATTERNS = [
    (re.compile(rf'(?P<dm>\b{_DAY}\s+(?:of\s+)?{_MONTH})\b', re.IGNORECASE),
     lambda m: (int(m.group('day')), _MONTHS[m.group('month').lower()])),
    (re.compile(rf'(?P<dm>\b{_MONTH}\s+{_DAY})\b', re.IGNORECASE),
     lambda m: (int(m.group('day')), _MONTHS[m.group('month').lower()])),
    # Indian numeric style: DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY
    (re.compile(r'(?P<dm>\b(?P<day>\d{1,2})[./-](?P<month>\d{1,2}))[./-](?:20)?\d{2}\b'),
     lambda m: (int(m.group('day')), int(m.group('month')))),
]


# Calendar tables keep the month in one column ("Sept", "Sept-Oct", "Oct / Nov") and the days
# in another as a range ("31-4"). Answers rewrite them as "31 Aug - 4 Sep".
_MONTH_WORD = re.compile(r'\b(' + '|'.join(sorted(_MONTHS, key=len, reverse=True)) + r')\b\.?',
                         re.IGNORECASE)
_DAY_RANGE = re.compile(r'(?<![\d/.,-])(\d{1,2})\s*[-–—]\s*(\d{1,2})(?![\d/.,-])')


def range_dates(text):
    """Dates a table row implies: a month word and a day range on one line.

    "Sept | 31-4" holds 31 Aug and 4 Sep: a range that runs backwards in number crosses
    into the next month. With two months on the row ("Sept-Oct | 28-3") the first day is
    in the first and the last in the second; when the numbers do not decide, either month
    is accepted. Only used for the sources: it explains how an answer could write a full
    date, it does not make a date in the answer count as written.
    """
    tokens = set()
    for line in text.splitlines():
        months = [_MONTHS[m.group(1).lower()] for m in _MONTH_WORD.finditer(line)]
        months = list(dict.fromkeys(months))
        if not months or len(months) > 2:
            continue
        for match in _DAY_RANGE.finditer(line):
            first, last = int(match.group(1)), int(match.group(2))
            if not (1 <= first <= 31 and 1 <= last <= 31):
                continue
            if len(months) == 1:
                month = months[0]
                start = month if first <= last else (month - 2) % 12 + 1
                pairs = [(start, first), (month, last)]
            elif first > last:
                pairs = [(months[0], first), (months[1], last)]
            else:
                pairs = [(m, day) for m in months for day in (first, last)]
            tokens |= {f'date:{m:02d}-{day:02d}' for m, day in pairs}
    return tokens


@dataclass
class Grounding:
    cited: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)

    @property
    def grounded(self):
        return not self.unsupported


def cited_numbers(answer, max_source):
    numbers = []
    for group in _CITATION.findall(answer):
        for part in group.split(','):
            number = int(part)
            if 1 <= number <= max_source and number not in numbers:
                numbers.append(number)
    return numbers


def _normalise(figure):
    return figure.replace(',', '')


def _date_tokens(text):
    """Calendar dates as 'date:MM-DD' tokens (the year, if any, is kept as a figure).

    Documents and answers write the same date many ways: "14th August 2026",
    "August 14, 2026", "14 Aug", "14.08.2026". Comparing them as tokens avoids flagging
    a correctly quoted date just because its format changed.
    """
    tokens, spans = set(), []
    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            day, month = order(match)
            if 1 <= day <= 31 and 1 <= month <= 12:
                tokens.add(f'date:{month:02d}-{day:02d}')
                spans.append(match.span('dm'))
    rest = list(text)
    for start, end in spans:
        rest[start:end] = ' ' * (end - start)
    return tokens, ''.join(rest)


def figures(text):
    text = _CITATION.sub(' ', text)
    # "2026-27", "2026–27", "2026/2027" and "2026�27" (a dash mangled by PDF extraction)
    # are one academic session, not the separate numbers 2026 and 27.
    sessions = {f'{m.group(1)}-{m.group(2)[-2:]}' for m in _SESSION.finditer(text)}
    rest = _SESSION.sub(' ', text)
    dates, rest = _date_tokens(rest)
    return sessions | dates | {_normalise(match) for match in _FIGURE.findall(rest)}


def check(answer, sources, question=''):
    cited = cited_numbers(answer, len(sources))
    # If the model cited nothing, check against everything it was given.
    pool = [s for s in sources if s.number in cited] or list(sources)
    available = set()
    for source in pool:
        # The model also sees each source's title, section and year (prompt.format_sources).
        header = ' '.join((source.title, source.heading_path, source.academic_year))
        available |= figures(f'{header}\n{source.content}') | range_dates(source.content)
    available |= figures(question)
    unsupported = sorted(
        figure for figure in figures(answer) if figure not in available and len(figure) > 1
    )
    return Grounding(cited=cited, unsupported=unsupported)
