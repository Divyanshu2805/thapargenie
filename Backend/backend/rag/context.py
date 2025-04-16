"""Turn ranked chunks into numbered sources for the answer prompt.

Adjacent chunks from one document are merged into a single source, so a fee table split
in two comes back whole under one citation number.
"""

from dataclasses import dataclass, field

from common.text import estimate_tokens

BUDGET_TOKENS = 6000


@dataclass
class Source:
    number: int
    document_id: str
    chunk_ids: list
    title: str
    url: str
    heading_path: str
    page_start: int | None
    page_end: int | None
    academic_year: str
    category: str
    is_current: bool
    source_type: str
    storage_path: str
    content: str
    score: float = 0.0
    parts: list = field(default_factory=list, repr=False)

    @property
    def tokens(self):
        return estimate_tokens(self.content)

    def public(self):
        """What the client may see about a source (no internal storage details)."""
        return {
            'position': self.number,
            'title': self.title,
            'url': self.url,
            'heading_path': self.heading_path,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'academic_year': self.academic_year,
            'category': self.category,
            'snippet': ' '.join(self.content.split())[:300],
        }


def build_sources(candidates, *, budget=BUDGET_TOKENS):
    """Ordered, numbered sources (best first) within the token budget."""
    # document -> {chunk_index: part}, plus each document's best score and first rank.
    documents = {}
    for rank, candidate in enumerate(candidates):
        doc = documents.setdefault(
            candidate.document_id,
            {'first': rank, 'score': candidate.score, 'meta': candidate, 'parts': {}},
        )
        doc['parts'][candidate.chunk_index] = {
            'id': candidate.chunk_id,
            'content': candidate.content,
            'heading_path': candidate.heading_path,
            'page_start': candidate.page_start,
            'page_end': candidate.page_end,
        }

    sources = []
    used = 0
    for doc in sorted(documents.values(), key=lambda d: d['first']):
        indexes = sorted(doc['parts'])
        # Split into runs of consecutive chunk indexes; each run becomes one source.
        runs, run = [], [indexes[0]]
        for index in indexes[1:]:
            if index == run[-1] + 1:
                run.append(index)
            else:
                runs.append(run)
                run = [index]
        runs.append(run)
        for run in runs:
            parts = [doc['parts'][i] for i in run]
            content = '\n\n'.join(part['content'] for part in parts)
            tokens = estimate_tokens(content)
            if sources and used + tokens > budget:
                continue
            meta = doc['meta']
            pages = [p for part in parts for p in (part['page_start'], part['page_end']) if p]
            sources.append(
                Source(
                    number=len(sources) + 1,
                    document_id=meta.document_id,
                    chunk_ids=[part['id'] for part in parts],
                    title=meta.title,
                    url=meta.url,
                    heading_path=parts[0]['heading_path'],
                    page_start=min(pages) if pages else None,
                    page_end=max(pages) if pages else None,
                    academic_year=meta.academic_year,
                    category=meta.category,
                    is_current=meta.is_current,
                    source_type=meta.source_type,
                    storage_path=meta.storage_path,
                    content=content,
                    score=doc['score'],
                    parts=parts,
                )
            )
            used += tokens
    return sources
