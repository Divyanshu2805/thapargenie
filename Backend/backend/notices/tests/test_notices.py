"""Notices: admins post them, students read them."""

from datetime import timedelta

from api.models import AuditEvent
from chat.models import ChatSettings
from common.tests.helpers import client_for, make_user
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from knowledge import services as knowledge
from knowledge.models import Document, DocumentStatus
from knowledge.storage import MemoryStorage, use_storage
from rest_framework.test import APIClient

from notices import retention, services
from notices.models import Notice

URL = '/api/v1/notices/'
OFFICIAL_URL = '/api/v1/notices/official/'
ADMIN_URL = '/api/v1/admin/notices/'
VALID = {
    'title': 'Hostel fee deadline extended',
    'body': 'The last date for the **hostel fee** is now 15 October.',
    'category': 'fees_scholarships',
    'link_url': 'https://www.thapar.edu/notices/hostel-fee',
}


def notice(**fields):
    fields = {'title': 'A notice', 'body': 'Body text.', **fields}
    return Notice.objects.create(**fields)


class NoticesTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = MemoryStorage()
        use_storage(self.storage)
        self.addCleanup(use_storage, None)
        ChatSettings.forget()
        self.addCleanup(ChatSettings.forget)
        self.now = timezone.now()
        self.admin = make_user('admin@thapar.edu', staff=True)
        self.admin_client = client_for(self.admin)
        self.student = make_user('student@thapar.edu')
        self.student_client = client_for(self.student)

    def post(self, **changes):
        return self.admin_client.post(ADMIN_URL, {**VALID, **changes}, format='json')

    def patch(self, item, **changes):
        return self.admin_client.patch(f'{ADMIN_URL}{item.pk}/', changes, format='json')

    def document_text(self, document):
        return self.storage.objects[document.storage_path][0].decode()


class StudentNoticeTests(NoticesTestCase):
    def test_only_visible_notices_pinned_first(self):
        old = notice(title='Old', publish_at=self.now - timedelta(days=3))
        new = notice(title='New', publish_at=self.now - timedelta(hours=1))
        pinned = notice(title='Pinned', is_pinned=True, publish_at=self.now - timedelta(days=9))
        notice(title='Draft', is_draft=True)
        notice(title='Scheduled', publish_at=self.now + timedelta(hours=2))
        notice(title='Expired', publish_at=self.now - timedelta(days=5),
               expires_at=self.now - timedelta(minutes=1))
        results = self.student_client.get(URL).data['results']
        self.assertEqual([item['id'] for item in results], [str(pinned.pk), str(new.pk),
                                                             str(old.pk)])
        self.assertNotIn('is_draft', results[0])
        self.assertNotIn('answerable', results[0])

    def test_category_filter(self):
        fees = notice(category='fees_scholarships')
        notice(category='hostel_campus_life')
        results = self.student_client.get(URL, {'category': 'fees_scholarships'}).data['results']
        self.assertEqual([item['id'] for item in results], [str(fees.pk)])
        self.assertEqual(self.student_client.get(URL, {'category': 'nope'}).status_code, 400)

    def test_needs_sign_in(self):
        for path in (URL, OFFICIAL_URL):
            self.assertIn(APIClient().get(path).status_code, (401, 403))

    def test_students_cannot_manage_notices(self):
        self.assertEqual(self.student_client.get(ADMIN_URL).status_code, 403)
        self.assertEqual(self.student_client.post(ADMIN_URL, VALID, format='json').status_code,
                         403)
        self.assertFalse(Notice.objects.exists())

    def test_app_config_fields(self):
        config = self.student_client.get('/api/v1/app-config/').data
        self.assertIsNone(config['latest_notice_at'])
        self.assertIsNone(config['important_notice'])

        notice(title='Normal', publish_at=self.now - timedelta(hours=2))
        important = notice(title='Exams moved', importance='important',
                           publish_at=self.now - timedelta(hours=3))
        notice(title='Later important', importance='important',
               publish_at=self.now + timedelta(hours=3))
        config = self.student_client.get('/api/v1/app-config/').data
        self.assertEqual(config['important_notice'],
                         {'id': str(important.pk), 'title': 'Exams moved'})
        self.assertEqual(config['latest_notice_at'], self.now - timedelta(hours=2))


class OfficialDocumentTests(NoticesTestCase):
    def document(self, title, *, days_ago=1, category='notices', **fields):
        fields = {'status': DocumentStatus.READY, 'is_current': True, 'source_type': 'url',
                  **fields}
        return Document.objects.create(
            title=title, content_hash=title, category=category,
            processed_at=self.now - timedelta(days=days_ago), **fields,
        )

    def test_lists_recent_ready_current_notice_documents(self):
        recent = self.document('Recent', source_url='https://www.thapar.edu/n1')
        self.document('Old', days_ago=40)
        self.document('Fees', category='fees_scholarships')
        self.document('Processing', status=DocumentStatus.PROCESSING)
        self.document('Not current', is_current=False)
        copy = self.document('Posted notice copy')
        notice(document=copy)

        results = self.student_client.get(OFFICIAL_URL).data['results']
        self.assertEqual([item['id'] for item in results], [str(recent.pk)])
        self.assertEqual(len(self.student_client.get(OFFICIAL_URL, {'days': 90}).data['results']),
                         2)
        for days in ('0', '91', 'x'):
            self.assertEqual(self.student_client.get(OFFICIAL_URL, {'days': days}).status_code,
                             400)

    def test_open_only_for_listed_documents(self):
        listed = self.document('Listed', source_url='https://www.thapar.edu/n1')
        fees = self.document('Fees', category='fees_scholarships',
                             source_url='https://www.thapar.edu/f')
        response = self.student_client.get(f'{OFFICIAL_URL}{listed.pk}/open/')
        self.assertEqual(response.data, {'url': 'https://www.thapar.edu/n1'})
        self.assertEqual(self.student_client.get(f'{OFFICIAL_URL}{fees.pk}/open/').status_code,
                         404)

    def test_open_signs_stored_files(self):
        stored = self.document('Scan', source_type='pdf', storage_path='documents/x.pdf',
                               original_filename='notice.pdf')
        self.storage.upload('documents/x.pdf', b'%PDF', 'application/pdf')
        response = self.student_client.get(f'{OFFICIAL_URL}{stored.pk}/open/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('url', response.data)

    def test_official_notice_counts_for_latest_notice_at(self):
        self.document('Recent', days_ago=0)
        config = self.student_client.get('/api/v1/app-config/').data
        self.assertIsNotNone(config['latest_notice_at'])


class AdminNoticeTests(NoticesTestCase):
    def test_create_published_adds_a_knowledge_copy(self):
        expires = self.now + timedelta(days=10)
        response = self.post(expires_at=expires.isoformat(), importance='important')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['state'], 'published')
        item = Notice.objects.get()
        document = item.document
        self.assertEqual((document.title, document.category, document.source_type),
                         (VALID['title'], 'fees_scholarships', 'text'))
        self.assertTrue(document.is_current)
        self.assertEqual(document.valid_until, timezone.localdate(expires))
        self.assertEqual(document.source_url, VALID['link_url'])
        text = self.document_text(document)
        self.assertIn('hostel fee', text)
        self.assertIn('Official notice: https://www.thapar.edu/notices/hostel-fee', text)
        self.assertEqual(response.data['document']['id'], str(document.pk))
        event = AuditEvent.objects.get(action='notice.created')
        self.assertEqual((event.actor, event.resource_id), (self.admin, str(item.pk)))

    def test_not_answerable_has_no_copy(self):
        self.assertEqual(self.post(answerable=False).status_code, 201)
        self.assertIsNone(Notice.objects.get().document)
        self.assertFalse(Document.objects.exists())

    def test_rejects_bad_input(self):
        past = (self.now - timedelta(hours=1)).isoformat()
        for changes in ({'link_url': 'http://www.thapar.edu/x'}, {'title': '  '},
                        {'title': 'x' * 161}, {'body': 'x' * 5001}, {'category': 'gossip'},
                        {'importance': 'urgent'}, {'expires_at': past}, {'extra': 1},
                        {'publish_at': (self.now + timedelta(days=5)).isoformat(),
                         'expires_at': (self.now + timedelta(days=4)).isoformat()}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 400)
        self.assertFalse(Notice.objects.exists())

    def test_draft_then_publish(self):
        self.post(is_draft=True, publish_at=(self.now - timedelta(days=2)).isoformat())
        item = Notice.objects.get()
        self.assertIsNone(item.document)
        self.assertEqual(self.student_client.get(URL).data['results'], [])

        response = self.patch(item, is_draft=False)
        self.assertEqual(response.data['state'], 'published')
        item.refresh_from_db()
        self.assertGreater(item.publish_at, self.now)  # posted now, so it shows as new
        self.assertIsNotNone(item.document)
        self.assertEqual(len(self.student_client.get(URL).data['results']), 1)

    def test_unpublish_and_answerable_off_remove_the_copy(self):
        self.post()
        item = Notice.objects.get()
        self.patch(item, is_draft=True)
        item.refresh_from_db()
        self.assertIsNone(item.document)
        self.assertFalse(Document.objects.exists())

        self.patch(item, is_draft=False)
        item.refresh_from_db()
        self.assertIsNotNone(item.document)
        self.patch(item, answerable=False)
        self.assertFalse(Document.objects.exists())

    def test_edit_updates_the_copy(self):
        self.post()
        item = Notice.objects.get()
        document = item.document
        Document.objects.filter(pk=document.pk).update(status=DocumentStatus.READY)
        response = self.patch(item, body='The deadline is now 20 October.', category='notices')
        self.assertEqual(response.status_code, 200, response.data)
        document.refresh_from_db()
        self.assertEqual(document.status, DocumentStatus.QUEUED)
        self.assertEqual(document.category, 'notices')
        self.assertIn('20 October', self.document_text(document))
        event = AuditEvent.objects.filter(action='notice.updated').get()
        self.assertEqual(event.metadata['fields'], ['body', 'category'])

    def test_edit_while_processing_is_caught_up_by_the_sweep(self):
        self.post()
        item = Notice.objects.get()
        Document.objects.filter(pk=item.document_id).update(status=DocumentStatus.PROCESSING)
        self.patch(item, body='Changed while processing.')
        document = Document.objects.get()
        self.assertNotIn('Changed while', self.document_text(document))
        self.assertEqual(services.sync_due_documents(), 0)  # still processing

        Document.objects.filter(pk=document.pk).update(status=DocumentStatus.READY)
        self.assertEqual(services.sync_due_documents(), 1)
        self.assertIn('Changed while', self.document_text(document))
        self.assertEqual(services.sync_due_documents(), 0)

    def test_duplicate_text_is_a_conflict(self):
        publish_at = (self.now - timedelta(minutes=5)).isoformat()
        self.assertEqual(self.post(publish_at=publish_at).status_code, 201)
        response = self.post(publish_at=publish_at)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'duplicate_document')
        self.assertEqual(Notice.objects.count(), 1)

    def test_scheduled_notice_gets_its_copy_when_due(self):
        publish_at = self.now + timedelta(hours=1)
        response = self.post(publish_at=publish_at.isoformat())
        self.assertEqual(response.data['state'], 'scheduled')
        self.assertFalse(Document.objects.exists())
        self.assertEqual(services.sync_due_documents(self.now), 0)
        self.assertEqual(services.sync_due_documents(publish_at + timedelta(minutes=1)), 1)
        self.assertTrue(Notice.objects.get().document.is_current)

    def test_expired_notice_copy_is_not_current(self):
        expires = self.now + timedelta(hours=1)
        self.post(expires_at=expires.isoformat())
        self.assertEqual(services.sync_due_documents(expires + timedelta(minutes=1)), 1)
        self.assertFalse(Notice.objects.get().document.is_current)
        self.assertEqual(services.sync_due_documents(expires + timedelta(minutes=6)), 0)

    def test_delete_needs_recent_sign_in(self):
        self.post()
        item = Notice.objects.get()
        stale = client_for(self.admin, signed_in_seconds_ago=3600)
        self.assertEqual(stale.delete(f'{ADMIN_URL}{item.pk}/').status_code, 403)
        self.assertTrue(Notice.objects.exists())

    def test_delete_keeps_the_copy_not_current_by_default(self):
        self.post()
        item = Notice.objects.get()
        self.assertEqual(self.admin_client.delete(f'{ADMIN_URL}{item.pk}/').status_code, 204)
        self.assertFalse(Notice.objects.exists())
        self.assertFalse(Document.objects.get().is_current)
        event = AuditEvent.objects.get(action='notice.deleted')
        self.assertFalse(event.metadata['document_deleted'])

    def test_delete_with_its_copy(self):
        self.post()
        item = Notice.objects.get()
        response = self.admin_client.delete(f'{ADMIN_URL}{item.pk}/?delete_document=true')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Document.objects.exists())

    def test_list_by_state_and_search(self):
        published = notice(title='Fee deadline', publish_at=self.now - timedelta(hours=1))
        scheduled = notice(title='Exam schedule', publish_at=self.now + timedelta(days=1))
        draft = notice(title='Draft', is_draft=True)
        expired = notice(title='Old', publish_at=self.now - timedelta(days=3),
                         expires_at=self.now - timedelta(days=1))
        for state, expected in (('published', published), ('scheduled', scheduled),
                                ('draft', draft), ('expired', expired)):
            with self.subTest(state=state):
                results = self.admin_client.get(ADMIN_URL, {'state': state}).data['results']
                self.assertEqual([item['id'] for item in results], [str(expected.pk)])
                self.assertEqual(results[0]['state'], state)
        self.assertEqual(self.admin_client.get(ADMIN_URL, {'state': 'nope'}).status_code, 400)
        results = self.admin_client.get(ADMIN_URL, {'q': 'deadline'}).data['results']
        self.assertEqual([item['id'] for item in results], [str(published.pk)])

    def test_editing_an_expired_notice_keeps_its_expiry(self):
        expired = notice(title='Old', publish_at=self.now - timedelta(days=3),
                         expires_at=self.now - timedelta(days=1))
        response = self.patch(expired, title='Old, renamed',
                              expires_at=expired.expires_at.isoformat())
        self.assertEqual(response.status_code, 200, response.data)


class RetentionTests(NoticesTestCase):
    @override_settings(RETENTION_NOTICE_DAYS=365)
    def test_purges_a_year_after_expiry(self):
        gone = notice(publish_at=self.now - timedelta(days=500),
                      expires_at=self.now - timedelta(days=366))
        kept = notice(publish_at=self.now - timedelta(days=500),
                      expires_at=self.now - timedelta(days=300))
        forever = notice(publish_at=self.now - timedelta(days=900))
        self.assertEqual(retention.purge(self.now, dry_run=True), 1)
        self.assertEqual(retention.purge(self.now), 1)
        self.assertEqual(set(Notice.objects.values_list('pk', flat=True)),
                         {kept.pk, forever.pk})
        self.assertFalse(Notice.objects.filter(pk=gone.pk).exists())


class ReplaceTextTests(NoticesTestCase):
    def test_only_text_documents(self):
        document = Document.objects.create(title='Page', source_type='url', content_hash='h',
                                           status=DocumentStatus.READY)
        with self.assertRaises(knowledge.InvalidTransition):
            knowledge.replace_text(document, 'new text', user=self.admin)
