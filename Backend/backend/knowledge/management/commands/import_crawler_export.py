from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from rag.llm import QuotaExhausted, RetryableError, get_llm

from knowledge.ingest.crawler_import import (
    DEFAULT_CATEGORIES,
    estimate,
    import_records,
    plan_import,
    read_records,
)


class Command(BaseCommand):
    help = 'Import chunks.jsonl.gz from the thapar.edu crawler export. Safe to re-run.'

    def add_arguments(self, parser):
        parser.add_argument('export_dir', help='Folder containing chunks.jsonl.gz')
        parser.add_argument(
            '--categories',
            default=','.join(DEFAULT_CATEGORIES),
            help='Comma-separated crawler categories to import.',
        )
        parser.add_argument('--include-review', action='store_true',
                            help='Also import rows the crawler marked "review".')
        parser.add_argument('--limit', type=int, help='Import at most N records (for trials).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be imported; call no APIs.')

    def handle(self, export_dir, categories, include_review, limit, dry_run, **options):
        path = Path(export_dir) / 'chunks.jsonl.gz'
        if not path.exists():
            raise CommandError(f'{path} not found.')
        wanted = {c.strip() for c in categories.split(',') if c.strip()}
        records = read_records(path, categories=wanted, include_review=include_review)
        if limit:
            records = records[:limit]

        pending, stats = plan_import(records)
        texts, tokens = estimate(pending)
        self.stdout.write(
            f'{len(records)} records selected; {stats.skipped} already imported; '
            f'{len(pending)} to import ({texts} chunks, ~{tokens:,} tokens).'
        )
        if dry_run or not pending:
            return

        def report(current, total):
            self.stdout.write(
                f'  {current.imported}/{total} records, {current.chunks} chunks', ending='\r'
            )
            self.stdout.flush()

        llm = get_llm()
        try:
            stats = import_records(records, llm, progress=report)
        except (QuotaExhausted, RetryableError) as exc:
            self.stdout.write('')
            raise CommandError(
                f'Stopped: {exc} Completed records are saved; run the command again later '
                'to continue.'
            ) from exc
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Imported {stats.imported} records ({stats.chunks} chunks), replaced '
                f'{stats.replaced}, skipped {stats.skipped}, empty {stats.empty}. '
                f'Embedding calls: {llm.usage.calls}.'
            )
        )
