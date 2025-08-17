import hashlib
from datetime import timedelta
from io import StringIO

from api.models import AuditActorKind, AuditEvent, AuditOutcome
from chat.models import AnswerCache, AnswerTrace, Conversation, Feedback, Message, UsageDaily
from chat.tests.test_chat import ChatTestCase, approved_user
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from knowledge.models import Document, DocumentStatus, SourceType
from knowledge.storage import MemoryStorage, StorageError, use_storage

LONG_AGO = timezone.now() - timedelta(days=400)


def age(queryset, **fields):
    """Backdate rows (auto_now fields can only be changed with update())."""
    queryset.update(**fields)


class PurgeDataTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.storage = MemoryStorage()
        use_storage(self.storage)
        self.addCleanup(use_storage, None)

    def purge(self, *args):
        out = StringIO()
        call_command('purge_data', *args, stdout=out)
        return out.getvalue()

    def failed_document(self, title, days_old):
        document = Document.objects.create(
            title=title, source_type=SourceType.PDF,
            content_hash=hashlib.sha256(title.encode()).hexdigest(),
            status=DocumentStatus.FAILED, storage_path=f'documents/{title}.pdf',
        )
        self.storage.upload(document.storage_path, b'%PDF', 'application/pdf')
        age(Document.objects.filter(pk=document.pk),
            updated_at=timezone.now() - timedelta(days=days_old))
        return document

    def test_inactive_conversations_are_deleted_with_everything_in_them(self):
        old = self.conversation()
        self.answered(old)
        Feedback.objects.create(message=Message.objects.get(conversation=old, role='assistant'),
                                user=self.user, rating=-1)
        recent = self.conversation()
        age(Conversation.objects.filter(pk=old.pk),
            last_message_at=timezone.now() - timedelta(days=181))

        output = self.purge()

        self.assertEqual(list(Conversation.objects.all()), [recent])
        self.assertFalse(Message.objects.filter(conversation_id=old.pk).exists())
        self.assertFalse(Feedback.objects.exists())
        self.assertIn('Deleted 1 conversations', output)

    def test_short_lived_rows_follow_their_own_periods(self):
        conversation = self.conversation()
        self.answered(conversation)
        age(AnswerTrace.objects.all(), created_at=timezone.now() - timedelta(days=31))
        AnswerCache.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        UsageDaily.objects.create(user=self.user, day=(timezone.now() - timedelta(days=401)).date())
        fresh_usage = UsageDaily.objects.filter(day=timezone.localdate()).count()

        self.purge()

        self.assertFalse(AnswerTrace.objects.exists())
        self.assertFalse(AnswerCache.objects.exists())
        self.assertEqual(UsageDaily.objects.count(), fresh_usage)
        # The conversation itself is recent and stays.
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_stuck_streams_are_marked_failed(self):
        conversation = self.conversation()
        stuck = Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT,
                                       status=Message.Status.STREAMING)
        age(Message.objects.filter(pk=stuck.pk), updated_at=timezone.now() - timedelta(hours=1))

        self.purge()

        stuck.refresh_from_db()
        self.assertEqual((stuck.status, stuck.error_code), (Message.Status.FAILED, 'interrupted'))

    def test_old_failed_documents_and_their_files_go_but_recent_ones_stay(self):
        old = self.failed_document('old-scan', days_old=31)
        recent = self.failed_document('new-scan', days_old=2)

        self.purge()

        self.assertFalse(Document.objects.filter(pk=old.pk).exists())
        self.assertTrue(Document.objects.filter(pk=recent.pk).exists())
        self.assertNotIn(old.storage_path, self.storage.objects)
        self.assertIn(recent.storage_path, self.storage.objects)

    def test_orphaned_files_are_swept_after_a_grace_period(self):
        self.storage.upload('documents/orphan.pdf', b'%PDF', 'application/pdf')
        self.storage.upload('documents/just-uploaded.pdf', b'%PDF', 'application/pdf')
        self.storage.created['documents/just-uploaded.pdf'] = timezone.now().isoformat()
        kept = self.failed_document('kept', days_old=1)

        self.purge()

        self.assertNotIn('documents/orphan.pdf', self.storage.objects)
        self.assertIn('documents/just-uploaded.pdf', self.storage.objects)
        self.assertIn(kept.storage_path, self.storage.objects)

    def test_old_audit_events_go_and_the_run_is_recorded(self):
        AuditEvent.objects.create(action='document.created', outcome=AuditOutcome.SUCCEEDED)
        age(AuditEvent.objects.all(), created_at=LONG_AGO)
        AuditEvent.objects.create(action='document.updated', outcome=AuditOutcome.SUCCEEDED)

        self.purge()

        actions = sorted(AuditEvent.objects.values_list('action', flat=True))
        self.assertEqual(actions, ['document.updated', 'retention.purged'])
        run = AuditEvent.objects.get(action='retention.purged')
        self.assertEqual(run.actor_kind, AuditActorKind.SERVICE)
        self.assertEqual(run.metadata['deleted']['audit_events'], 1)

    def test_dry_run_changes_nothing(self):
        old = self.conversation()
        age(Conversation.objects.filter(pk=old.pk), last_message_at=LONG_AGO)
        self.failed_document('old-scan', days_old=90)
        self.storage.upload('documents/orphan.pdf', b'%PDF', 'application/pdf')

        output = self.purge('--dry-run')

        self.assertIn('Would delete 1 conversations', output)
        self.assertIn('Would delete 1 orphaned files', output)
        self.assertTrue(Conversation.objects.filter(pk=old.pk).exists())
        self.assertEqual(Document.objects.filter(status=DocumentStatus.FAILED).count(), 1)
        self.assertIn('documents/orphan.pdf', self.storage.objects)
        self.assertFalse(AuditEvent.objects.filter(action='retention.purged').exists())

    @override_settings(RETENTION_CONVERSATION_DAYS=7)
    def test_periods_come_from_settings(self):
        other = approved_user('b@thapar.edu')
        conversation = self.conversation(user=other)
        age(Conversation.objects.filter(pk=conversation.pk),
            last_message_at=timezone.now() - timedelta(days=8))
        self.purge('--skip-storage')
        self.assertFalse(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_a_storage_outage_does_not_undo_the_database_purge(self):
        old = self.failed_document('old-scan', days_old=31)

        def broken_delete(paths):
            raise StorageError('down')

        self.storage.delete = broken_delete
        self.purge('--skip-storage')
        self.assertFalse(Document.objects.filter(pk=old.pk).exists())
