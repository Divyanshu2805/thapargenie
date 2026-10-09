"""Keep web pages added by URL in step with the live site.

A page added from Admin -> Knowledge is fetched once. This checks each of them again,
and re-processes only the ones whose readable text changed: the page is fetched,
reduced to its text (menus, scripts and markup are dropped, so a changed tracking
token is not a change) and compared with a fingerprint kept in `document.metadata`.

Crawler-imported pages have no stored source and are not covered; they change by
importing a new export.
"""

import logging
import time
from dataclasses import dataclass, field

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from common.safe_http import FetchError, UnsafeURLError, fetch
from django.conf import settings
from django.utils import timezone

from knowledge.ingest.extract import extract_html
from knowledge.ingest.filetypes import UnsupportedFile, decode_text
from knowledge.ingest.pipeline import page_fingerprint, process_document
from knowledge.models import Document, DocumentStatus, SourceType

logger = logging.getLogger(__name__)

FINGERPRINT = 'page_fingerprint'
CHECKED_AT = 'page_checked_at'
CHECK_ERROR = 'page_check_error'


@dataclass
class RefreshStats:
    checked: int = 0
    unchanged: int = 0
    changed: int = 0
    first_seen: int = 0
    failed: int = 0
    changed_titles: list = field(default_factory=list)


def _live_fingerprint(document, fetcher):
    result = fetcher(document.source_url, max_bytes=settings.INGEST_MAX_FILE_MB * 1024 * 1024)
    page = extract_html(decode_text(result.content), url=document.source_url)
    return page_fingerprint(page.markdown)


def _remember(document, **values):
    document.metadata = {**document.metadata, **values}
    Document.objects.filter(pk=document.pk).update(metadata=document.metadata)


def refresh_web_pages(*, dry_run=False, limit=None, delay=1.0, fetcher=None, sleep=time.sleep,
                      llm=None):
    """Check every ready web page; re-process the changed ones. Returns RefreshStats.

    A page that cannot be fetched or read keeps its stored passages and is counted as
    failed. A page seen for the first time only gets its fingerprint recorded. With
    `dry_run` nothing is saved or re-processed.
    """
    fetcher = fetcher or fetch
    stats = RefreshStats()
    documents = Document.objects.filter(
        source_type=SourceType.URL, status=DocumentStatus.READY
    ).order_by('created_at')
    for document in documents[:limit] if limit else documents:
        if stats.checked:
            sleep(delay)  # be polite to the site
        stats.checked += 1
        now = timezone.now().isoformat(timespec='seconds')
        try:
            live = _live_fingerprint(document, fetcher)
        except (FetchError, UnsafeURLError, UnsupportedFile) as exc:
            stats.failed += 1
            logger.warning('Page check failed for %s: %s', document.pk, exc)
            if not dry_run:
                _remember(document, **{CHECKED_AT: now, CHECK_ERROR: str(exc)[:200]})
            continue
        stored = document.metadata.get(FINGERPRINT)
        if stored == live:
            stats.unchanged += 1
            if not dry_run:
                _remember(document, **{CHECKED_AT: now, CHECK_ERROR: ''})
            continue
        if stored is None:
            stats.first_seen += 1
            if not dry_run:
                _remember(document, **{FINGERPRINT: live, CHECKED_AT: now, CHECK_ERROR: ''})
            continue
        stats.changed += 1
        stats.changed_titles.append(document.title)
        if dry_run:
            continue
        _remember(document, **{CHECKED_AT: now, CHECK_ERROR: ''})
        Document.objects.filter(pk=document.pk).update(
            status=DocumentStatus.QUEUED, status_detail='The page changed; reading it again'
        )
        AuditEvent.objects.create(
            actor=None,
            actor_kind=AuditActorKind.SERVICE,
            action='document.refreshed',
            resource_type='document',
            resource_id=str(document.pk),
            outcome=AuditOutcome.SUCCEEDED,
            metadata={'reason': 'page_changed'},
        )
        # Processing fetches the page again and records the new fingerprint. If it fails,
        # the stored passages stay searchable and the document shows as failed for an admin.
        processed = process_document(document.pk, llm=llm)
        if processed is not None and processed.status != DocumentStatus.READY:
            logger.warning('Re-reading %s failed: %s', document.pk, processed.error)
    return stats
