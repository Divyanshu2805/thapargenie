from django.core.management.base import BaseCommand

from knowledge.services import expire_due_documents


class Command(BaseCommand):
    help = 'Mark documents whose "valid until" date has passed as not current.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Only count the documents that are due.')

    def handle(self, dry_run, **options):
        count = expire_due_documents(dry_run=dry_run)
        verb = 'due to expire' if dry_run else 'marked not current'
        self.stdout.write(self.style.SUCCESS(f'{count} documents {verb}.'))
