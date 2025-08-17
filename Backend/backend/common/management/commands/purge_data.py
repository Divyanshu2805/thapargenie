"""Apply the retention policy. Run daily by the maintenance workflow."""

from chat import retention as chat_retention
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from knowledge import retention as knowledge_retention
from knowledge.storage import StorageError
from notices import retention as notice_retention

from common import retention as audit_retention


class Command(BaseCommand):
    help = 'Delete data past its retention period. Idempotent; safe to run at any time.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be deleted without deleting it.')
        parser.add_argument('--skip-storage', action='store_true',
                            help='Do not sweep orphaned files in storage.')

    def handle(self, *args, dry_run=False, skip_storage=False, **options):
        now = timezone.now()
        results = chat_retention.purge(now, dry_run=dry_run)
        results['notices'] = notice_retention.purge(now, dry_run=dry_run)
        results['failed_documents'] = knowledge_retention.purge_failed_documents(
            now, dry_run=dry_run
        )
        if not skip_storage:
            try:
                results['orphaned_files'] = knowledge_retention.purge_orphaned_files(
                    now, dry_run=dry_run
                )
            except StorageError as exc:
                raise CommandError(f'Storage sweep failed: {exc}') from exc
        results['audit_events'] = audit_retention.purge_audit_events(now, dry_run=dry_run)

        if not dry_run:
            audit_retention.record_purge(results)
        for rule, count in results.items():
            if rule == 'stale_streams':
                verb = 'Would mark' if dry_run else 'Marked'
                self.stdout.write(f'{verb} {count} stuck answers as failed')
            else:
                verb = 'Would delete' if dry_run else 'Deleted'
                self.stdout.write(f'{verb} {count} {rule.replace("_", " ")}')
