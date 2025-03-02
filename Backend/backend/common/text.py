import re
import unicodedata

_WHITESPACE = re.compile(r'[ \t\f\v]+')
_BLANK_LINES = re.compile(r'\n{3,}')


def normalize_text(text):
    """NFKC, unified newlines, collapsed runs of spaces and blank lines."""
    text = unicodedata.normalize('NFKC', text or '')
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\x00', '')
    text = '\n'.join(_WHITESPACE.sub(' ', line).strip() for line in text.split('\n'))
    return _BLANK_LINES.sub('\n\n', text).strip()


def estimate_tokens(text):
    """Cheap token estimate (~4 chars per token) for budgeting, not billing."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def truncate(text, limit, suffix='…'):
    """Cut at a word boundary so the result is at most `limit` characters."""
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - len(suffix))]
    space = cut.rfind(' ')
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip() + suffix
