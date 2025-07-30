"""Document "valid until" dates: admin edits, automatic expiry, list filter, Overview."""

import io
from datetime import timedelta

from api.models import AuditActorKind, AuditEvent
from django.core.management import call_command
from django.utils import timezone

from knowledge import services
from knowledge.models import Chunk, Document
from knowledge.tests.test_admin_api import BASE, AdminKnowledgeTestCase


def days(offset):
    return timezone.localdate() + timedelta(days=offset)


class ValidUntilEditTests(AdminKnowledgeTestCase):
    def patch(self, document, body):
        return self.client.patch(f'{BASE}/documents/{document.pk}/', body, format='json')

    def test_a_future_date_is_saved_and_keeps_the_document_current(self):
        document = self.ready_document()
        response = self.patch(document, {'valid_until': days(10).isoformat()})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['valid_until'], days(10).isoformat())
        self.assertTrue(response.data['is_current'])

    def test_a_past_date_marks_the_document_and_its_passages_not_current(self):
        document = self.ready_document()
        response = self.patch(document, {'valid_until': days(-1).isoformat()})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['is_current'])
        self.assertFalse(Chunk.objects.get(document=document).is_current)
        event = AuditEvent.objects.get(action='document.updated', actor=self.admin)
        self.assertEqual(event.metadata['fields'], ['is_current', 'valid_until'])

    def test_today_is_still_valid(self):
        document = self.ready_document()
        response = self.patch(document, {'valid_until': days(0).isoformat()})
        self.assertTrue(response.data['is_current'])

    def test_marking_current_with_a_past_date_is_refused(self):
        document = self.ready_document()
        response = self.patch(document, {'valid_until': days(-1).isoformat(), 'is_current': True})
        self.assertEqual(response.status_code, 400)
        self.assertIn('is_current', response.data['error']['fields'])
        document.refresh_from_db()
        self.assertIsNone(document.valid_until)
        self.assertTrue(document.is_current)

    def test_extending_the_date_does_not_mark_it_current_again(self):
        document = self.ready_document()
        self.patch(document, {'valid_until': days(-1).isoformat()})
        response = self.patch(document, {'valid_until': days(30).isoformat()})
        self.assertFalse(response.data['is_current'])
        response = self.patch(document, {'is_current': True})
        self.assertTrue(response.data['is_current'])

    def test_valid_until_cannot_precede_the_effective_date(self):
        document = self.ready_document()
        response = self.patch(document, {'effective_date': days(5).isoformat(),
                                         'valid_until': days(1).isoformat()})
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid_until', response.data['error']['fields'])

        # Only one of the two in the request: the stored effective date is checked too.
        self.patch(document, {'effective_date': days(5).isoformat()})
        response = self.patch(document, {'valid_until': days(1).isoformat()})
        self.assertEqual(response.status_code, 400)
        document.refresh_from_db()
        self.assertIsNone(document.valid_until)

    def test_a_document_added_with_a_past_date_starts_not_current(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(f'{BASE}/documents/text/', {
                'title': 'Old calendar', 'text': 'Mid sems in March.', 'is_current': True,
                'valid_until': days(-3).isoformat(),
            }, format='json')
        self.assertEqual(response.status_code, 202, response.data)
        self.assertFalse(response.data['is_current'])


class ExpirySweepTests(AdminKnowledgeTestCase):
    def document_valid_until(self, title, offset):
        document = self.ready_document(title=title, text=f'{title} text.')
        # Set directly, as if the date passed since it was saved.
        Document.objects.filter(pk=document.pk).update(valid_until=days(offset))
        return document

    def test_only_documents_past_their_date_expire_once(self):
        past = self.document_valid_until('Past', -1)
        today = self.document_valid_until('Today', 0)
        future = self.document_valid_until('Future', 3)
        self.changes.clear()

        self.assertEqual(services.expire_due_documents(dry_run=True), 1)
        self.assertTrue(Document.objects.get(pk=past.pk).is_current)

        self.assertEqual(services.expire_due_documents(), 1)
        self.assertEqual(
            {d.title: d.is_current for d in Document.objects.all()},
            {'Past': False, 'Today': True, 'Future': True},
        )
        self.assertFalse(Chunk.objects.get(document=past).is_current)
        self.assertTrue(Chunk.objects.get(document=today).is_current)
        self.assertTrue(Chunk.objects.get(document=future).is_current)
        event = AuditEvent.objects.get(action='document.expired')
        self.assertEqual((event.actor, event.actor_kind, event.resource_id),
                         (None, AuditActorKind.SERVICE, str(past.pk)))
        self.assertEqual(event.metadata, {'valid_until': days(-1).isoformat()})
        self.assertEqual(len(self.changes), 1)  # the answer cache is cleared once

        self.assertEqual(services.expire_due_documents(), 0)
        self.assertEqual(AuditEvent.objects.filter(action='document.expired').count(), 1)
        self.assertEqual(len(self.changes), 1)

    def test_command(self):
        self.document_valid_until('Past', -2)
        out = io.StringIO()
        call_command('expire_documents', '--dry-run', stdout=out)
        self.assertIn('1 documents due to expire', out.getvalue())
        call_command('expire_documents', stdout=out)
        self.assertIn('1 documents marked not current', out.getvalue())
        self.assertFalse(Document.objects.get().is_current)


class ValidityListAndOverviewTests(AdminKnowledgeTestCase):
    def setUp(self):
        super().setUp()
        for title, offset in (('Expired', -1), ('Soon', 3), ('Later', 20), ('Far', 90)):
            document = self.ready_document(title=title, text=f'{title} text.')
            Document.objects.filter(pk=document.pk).update(valid_until=days(offset))
        self.ready_document(title='Undated', text='Undated text.')

    def titles(self, **params):
        response = self.client.get(f'{BASE}/documents/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return sorted(d['title'] for d in response.data['results'])

    def test_list_filter(self):
        self.assertEqual(self.titles(validity='expiring'), ['Later', 'Soon'])
        self.assertEqual(self.titles(validity='expired'), ['Expired'])
        self.assertEqual(len(self.titles()), 5)
        response = self.client.get(f'{BASE}/documents/', {'validity': 'soon'})
        self.assertEqual(response.status_code, 400)

    def test_overview_lists_the_soonest(self):
        knowledge = self.client.get(f'{BASE}/stats/').data['knowledge']
        self.assertEqual(knowledge['expiring_soon'], 2)
        self.assertEqual(knowledge['expired'], 1)
        self.assertEqual([item['title'] for item in knowledge['expiring']], ['Soon', 'Later'])
        self.assertEqual(knowledge['expiring'][0]['valid_until'], days(3).isoformat())
