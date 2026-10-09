from django.core.management.base import BaseCommand

from knowledge.refresh import refresh_web_pages


class Command(BaseCommand):
    help = (
        'Fetch every web page that was added by URL and re-process the ones whose text '
        'changed. Run with --dry-run first to see what would be re-read.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Only report; save nothing and re-process nothing.')
        parser.add_argument('--limit', type=int, help='Check at most N pages.')
        parser.add_argument('--delay', type=float, default=1.0,
                            help='Seconds to wait between pages (default 1).')

    def handle(self, dry_run, limit, delay, **options):
        stats = refresh_web_pages(dry_run=dry_run, limit=limit, delay=delay)
        for title in stats.changed_titles:
            self.stdout.write(f'  changed: {title[:80]}')
        verb = 'would be re-read' if dry_run else 're-read'
        self.stdout.write(self.style.SUCCESS(
            f'Checked {stats.checked} pages: {stats.changed} changed ({verb}), '
            f'{stats.unchanged} unchanged, {stats.first_seen} seen for the first time, '
            f'{stats.failed} could not be fetched.'
        ))
