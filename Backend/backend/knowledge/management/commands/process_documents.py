from django.core.management.base import BaseCommand

from knowledge.ingest.pipeline import process_document
from knowledge.jobs import STALE_AFTER
from knowledge.models import Document, DocumentStatus


class Command(BaseCommand):
    help = 'Process queued documents now (and re-queue ones stuck in processing).'

    def add_arguments(self, parser):
        parser.add_argument('--reembed', action='store_true',
                            help='Queue every ready document for re-embedding first '
                                 '(after changing EMBED_PROVIDER or EMBED_MODEL).')

    def handle(self, reembed, **options):
        from django.utils import timezone

        if reembed:
            count = Document.objects.filter(status=DocumentStatus.READY).update(
                status=DocumentStatus.QUEUED, status_detail='Queued for re-embedding'
            )
            self.stdout.write(f'Queued {count} documents for re-embedding.')
        Document.objects.filter(
            status=DocumentStatus.PROCESSING, updated_at__lt=timezone.now() - STALE_AFTER
        ).update(status=DocumentStatus.QUEUED)

        queued = Document.objects.filter(status=DocumentStatus.QUEUED)
        ids = list(queued.values_list('pk', flat=True))
        for number, document_id in enumerate(ids, start=1):
            document = process_document(document_id)
            if document is None:
                continue
            outcome = document.status if not document.error else f'failed: {document.error}'
            self.stdout.write(f'[{number}/{len(ids)}] {document.title[:60]} -> {outcome}')
        self.stdout.write(self.style.SUCCESS(f'Done: {len(ids)} documents.'))
