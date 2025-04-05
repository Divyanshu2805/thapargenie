"""Split Markdown into retrieval chunks.

Rules:
- Heading lines update a breadcrumb (`Fees › Hostel › 2026-27`) stored on every chunk.
- Prose is packed to about `target` tokens, with a short overlap between neighbours
  in the same section so a sentence cut at a boundary is still findable.
- Tables are never mixed into the middle of prose and never split without repeating
  the header row, so every piece of a fee table still says what its columns mean.
- `[[page N]]` markers set page numbers and are removed from the text.
"""

import re
from dataclasses import dataclass, field

from common.text import estimate_tokens

TARGET_TOKENS = 450
OVERLAP_TOKENS = 60
TABLE_MAX_TOKENS = 1200
MAX_CHUNK_CHARS = 11_000

_HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*#*$')
_PAGE = re.compile(r'^\[\[?page\s+(\d+)\]\]?$', re.IGNORECASE)
_TABLE_SEPARATOR = re.compile(r'^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$')
_SENTENCE_END = re.compile(r'(?<=[.!?;:])\s+')


@dataclass
class Block:
    kind: str  # 'text' | 'table'
    lines: list[str]
    headings: tuple[str, ...]
    page_start: int | None
    page_end: int | None

    @property
    def text(self):
        return '\n'.join(self.lines)

    @property
    def tokens(self):
        return estimate_tokens(self.text)


@dataclass
class ChunkDraft:
    content: str
    heading_path: str
    page_start: int | None
    page_end: int | None
    token_count: int = field(init=False)

    def __post_init__(self):
        self.token_count = estimate_tokens(self.content)


def _is_table_line(line):
    return line.startswith('|')


def parse_blocks(markdown):
    blocks = []
    headings = []
    page = None
    buffer = []
    buffer_kind = None
    buffer_start = None

    def flush():
        nonlocal buffer, buffer_kind, buffer_start
        if buffer:
            blocks.append(Block(buffer_kind, buffer, tuple(headings), buffer_start, page))
        buffer, buffer_kind, buffer_start = [], None, None

    for raw in markdown.split('\n'):
        line = raw.rstrip()
        page_match = _PAGE.match(line.strip())
        if page_match:
            if buffer_kind == 'text':
                flush()
            page = int(page_match.group(1))
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            del headings[level - 1 :]
            headings.extend([''] * (level - 1 - len(headings)))
            headings.append(heading.group(2).strip())
            continue
        if not line.strip():
            if buffer_kind == 'text':
                flush()
            continue
        kind = 'table' if _is_table_line(line.strip()) else 'text'
        if kind != buffer_kind:
            flush()
            buffer_kind, buffer_start = kind, page
        buffer.append(line.strip())
    flush()
    return blocks


def _split_long_text(text, limit):
    """Split an oversized paragraph on sentence boundaries (words as a last resort)."""
    pieces, current = [], ''
    for sentence in _SENTENCE_END.split(text):
        candidate = f'{current} {sentence}'.strip()
        if current and estimate_tokens(candidate) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    result = []
    for piece in pieces:
        while estimate_tokens(piece) > limit * 1.5:
            cut = piece.rfind(' ', 0, limit * 4) or limit * 4
            result.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        result.append(piece)
    return result


def _split_table(block, limit):
    lines = block.lines
    has_header = len(lines) > 1 and _TABLE_SEPARATOR.match(lines[1].replace(' ', ''))
    header = lines[:2] if has_header else []
    rows = lines[2:] if has_header else lines
    pieces, current = [], []
    for row in rows:
        candidate = header + current + [row]
        if current and estimate_tokens('\n'.join(candidate)) > limit:
            pieces.append(header + current)
            current = []
        current.append(row)
    if current or not pieces:
        pieces.append(header + current)
    return ['\n'.join(piece) for piece in pieces]


def _overlap_tail(text, tokens):
    sentences = _SENTENCE_END.split(text)
    tail = []
    for sentence in reversed(sentences):
        tail.insert(0, sentence)
        if estimate_tokens(' '.join(tail)) >= tokens:
            break
    tail_text = ' '.join(tail)
    return tail_text if len(tail) < len(sentences) else ''


def breadcrumb(headings):
    return ' › '.join(h for h in headings if h)


def build_chunks(
    markdown,
    *,
    target=TARGET_TOKENS,
    overlap=OVERLAP_TOKENS,
    table_max=TABLE_MAX_TOKENS,
):
    drafts = []
    parts, part_tokens = [], 0
    section = None
    pages = [None, None]

    def emit(content, headings, start, end):
        content = content.strip()
        if not content:
            return
        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS]
        drafts.append(ChunkDraft(content, breadcrumb(headings), start, end))

    def flush(keep_overlap):
        nonlocal parts, part_tokens
        if not parts:
            return
        text = '\n\n'.join(parts)
        emit(text, section, pages[0], pages[1])
        tail = _overlap_tail(parts[-1], overlap) if keep_overlap and overlap else ''
        parts = [tail] if tail else []
        part_tokens = estimate_tokens(tail) if tail else 0
        pages[0] = pages[1] if tail else None

    def track_pages(block):
        if pages[0] is None:
            pages[0] = block.page_start
        pages[1] = block.page_end if block.page_end is not None else pages[1]

    for block in parse_blocks(markdown):
        if block.headings != section:
            # New section: never carry overlap across it.
            flush(keep_overlap=False)
            section = block.headings

        if block.kind == 'table':
            flush(keep_overlap=False)
            limit = table_max if block.tokens <= table_max else target
            for piece in _split_table(block, limit):
                emit(piece, section, block.page_start, block.page_end)
            continue

        texts = [block.text] if block.tokens <= target else _split_long_text(block.text, target)
        for text in texts:
            tokens = estimate_tokens(text)
            if parts and part_tokens + tokens > target:
                flush(keep_overlap=True)
            track_pages(block)
            parts.append(text)
            part_tokens += tokens

    flush(keep_overlap=False)
    return drafts


def search_header(*, title, category_label, department='', heading_path='', academic_year=''):
    """First line of every chunk's search text: gives isolated chunks their context."""
    fields = [title, category_label, department, heading_path, academic_year]
    return ' | '.join(field for field in fields if field)
