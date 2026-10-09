from django.core.management.base import BaseCommand, CommandError
from rag.llm import QuotaExhausted, RetryableError, get_llm

from knowledge.ingest.backfill import backfill_context


class Command(BaseCommand):
    help = (
        'Write a sentence of context for every stored chunk that has none, and re-embed '
        'those chunks. Run with --dry-run first to see how many model calls it needs.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Process at most N documents (a trial).')
        parser.add_argument('--title', default='', help='Only documents whose title contains this.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Count what would be done; call no APIs and save nothing.')
        parser.add_argument('--include-long', action='store_true',
                            help='Also process pages with more than 150 chunks (many calls each).')

    def handle(self, limit, title, dry_run, include_long, **options):
        def report(stats):
            self.stdout.write(f'  {stats.documents} documents, {stats.chunks} chunks', ending='\r')
            self.stdout.flush()

        llm = None if dry_run else get_llm()
        try:
            stats = backfill_context(llm, limit=limit, title_contains=title, dry_run=dry_run,
                                     progress=None if dry_run else report,
                                     include_long=include_long)
        except (QuotaExhausted, RetryableError) as exc:
            self.stdout.write('')
            raise CommandError(
                f'Stopped: {exc} Finished documents are saved; run the command again later '
                'to continue.'
            ) from exc
        self.stdout.write('')
        verb = 'Would process' if dry_run else 'Processed'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {stats.documents} documents ({stats.chunks} chunks, '
            f'~{stats.model_calls} fast-model calls and one embedding per chunk). '
            f'Already had context: {stats.already_done}. Skipped as long: {stats.too_long}'
            f'{"" if include_long or not stats.too_long else " (add --include-long)"}.'
        ))
