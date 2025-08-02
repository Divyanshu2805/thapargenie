"""Bulk document actions: one request, each document through its own service call."""

import uuid
from datetime import timedelta
from unittest import mock

from api.models import AuditEvent
from common.tests.helpers import client_for, make_user
from django.utils import timezone

from knowledge import services
from knowledge.models import Chunk, Document, DocumentStatus
from knowledge.tests.test_admin_api import BASE, AdminKnowledgeTestCase

URL = f'{BASE}/documents/bulk/'


class BulkActionTests(AdminKnowledgeTestCase):
    def setUp(self):
        super().setUp()
        self.first = self.ready_document(title='Fees 2025-26', text='Fee is Rs 1,00,000.')
        self.second = self.ready_document(title='Hostel 2025-26', text='Hostel is Rs 90,000.')
        self.ids = [str(self.first.pk), str(self.second.pk)]

    def bulk(self, body, client=None):
        return (client or self.client).post(URL, body, format='json')

    def test_update_sets_fields_on_every_document(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.bulk({'action': 'update', 'ids': self.ids,
                                  'changes': {'is_current': False, 'valid_until': None}})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {'succeeded': self.ids, 'failed': []})
        self.assertFalse(Document.objects.filter(is_current=True).exists())
        self.assertFalse(Chunk.objects.filter(is_current=True).exists())
        events = AuditEvent.objects.filter(action='document.updated')
        self.assertEqual(events.count(), 2)
        self.assertEqual(len({event.request_id for event in events}), 1)

    def test_a_search_field_change_reprocesses_ready_documents(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.bulk({'action': 'update', 'ids': self.ids,
                                  'changes': {'academic_year': '2026-27'}})
        self.assertEqual(response.data['failed'], [])
        self.assertEqual(
            set(Document.objects.values_list('academic_year', 'status')),
            {('2026-27', DocumentStatus.QUEUED)},
        )

    def test_one_bad_document_does_not_block_the_rest(self):
        # The first already starts after the new "valid until": a per-document failure.
        Document.objects.filter(pk=self.first.pk).update(
            effective_date=timezone.localdate() + timedelta(days=60))
        missing = str(uuid.uuid4())
        response = self.bulk({'action': 'update', 'ids': [*self.ids, missing],
                              'changes': {'valid_until': (timezone.localdate()
                                                          + timedelta(days=30)).isoformat()}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['succeeded'], [str(self.second.pk)])
        failures = {item['id']: item['code'] for item in response.data['failed']}
        self.assertEqual(failures, {str(self.first.pk): 'validation_error', missing: 'not_found'})
        self.assertTrue(all(item['message'] for item in response.data['failed']))
        self.first.refresh_from_db()
        self.assertIsNone(self.first.valid_until)

    def test_disable_enable_and_invalid_transitions(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.bulk({'action': 'disable', 'ids': self.ids})
        self.assertEqual(response.data['succeeded'], self.ids)
        self.assertFalse(Chunk.objects.filter(is_searchable=True).exists())

        response = self.bulk({'action': 'disable', 'ids': self.ids[:1]})
        self.assertEqual(response.data['failed'][0]['code'], 'invalid_transition')

        with self.captureOnCommitCallbacks(execute=True):
            response = self.bulk({'action': 'enable', 'ids': self.ids})
        self.assertEqual(response.data['succeeded'], self.ids)
        self.assertEqual(Chunk.objects.filter(is_searchable=True).count(), 2)

    def test_reprocess_queues_each_document(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.bulk({'action': 'reprocess', 'ids': self.ids})
        self.assertEqual(response.data['succeeded'], self.ids)
        self.assertEqual(set(Document.objects.values_list('status', flat=True)),
                         {DocumentStatus.QUEUED})
        self.assertEqual(AuditEvent.objects.filter(action='document.reprocessed').count(), 2)

    def test_delete_needs_a_recent_sign_in_and_is_all_or_nothing(self):
        stale = client_for(self.admin, signed_in_seconds_ago=3600)
        response = self.bulk({'action': 'delete', 'ids': self.ids}, client=stale)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'recent_auth_required')
        self.assertEqual(Document.objects.count(), 2)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.bulk({'action': 'delete', 'ids': self.ids})
        self.assertEqual(response.data['succeeded'], self.ids)
        self.assertFalse(Document.objects.exists())
        self.assertEqual(AuditEvent.objects.filter(action='document.deleted').count(), 2)

    def test_request_validation(self):
        too_many = [str(uuid.uuid4()) for _ in range(101)]
        for body, field in (
            ({'action': 'archive', 'ids': self.ids}, 'action'),
            ({'action': 'enable', 'ids': []}, 'ids'),
            ({'action': 'enable', 'ids': too_many}, 'ids'),
            ({'action': 'enable', 'ids': ['not-a-uuid']}, 'ids'),
            ({'action': 'update', 'ids': self.ids}, 'changes'),
            ({'action': 'update', 'ids': self.ids, 'changes': {}}, 'changes'),
            ({'action': 'enable', 'ids': self.ids, 'changes': {'is_current': True}}, 'changes'),
            ({'action': 'update', 'ids': self.ids, 'changes': {'title': 'Same for all'}},
             'changes'),
            ({'action': 'update', 'ids': self.ids, 'changes': {'academic_year': '2026'}},
             'changes'),
            ({'action': 'enable', 'ids': self.ids, 'extra': 1}, 'extra'),
        ):
            response = self.bulk(body)
            self.assertEqual(response.status_code, 400, body)
            self.assertIn(field, response.data['error']['fields'], body)

    def test_repeated_ids_are_applied_once(self):
        with self.captureOnCommitCallbacks(execute=False):
            response = self.bulk({'action': 'reprocess', 'ids': [self.ids[0], self.ids[0]]})
        self.assertEqual(response.data['succeeded'], [self.ids[0]])

    def test_matching_ids_follow_the_list_filters(self):
        with self.captureOnCommitCallbacks(execute=False):
            services.create_from_text(title='Calendar', text='Mid sems in October.',
                                      meta={'category': 'academic_calendar'}, user=self.admin)
        url = f'{BASE}/documents/ids/'
        everything = self.client.get(url).data
        self.assertEqual((everything['count'], len(everything['ids']), everything['truncated']),
                         (3, 3, False))
        ready = self.client.get(url, {'status': 'ready', 'q': 'hostel'}).data
        self.assertEqual(ready['ids'], [str(self.second.pk)])
        listed = self.client.get(f'{BASE}/documents/', {'status': 'ready'}).data['results']
        self.assertEqual(set(self.client.get(url, {'status': 'ready'}).data['ids']),
                         {d['id'] for d in listed})
        self.assertEqual(self.client.get(url, {'status': 'nope'}).status_code, 400)

    def test_matching_ids_are_capped(self):
        with mock.patch('knowledge.admin_views.MAX_MATCHING_IDS', 1):
            data = self.client.get(f'{BASE}/documents/ids/').data
        self.assertEqual((data['count'], len(data['ids']), data['truncated']), (2, 1, True))
        self.assertEqual(data['ids'], [str(self.second.pk)])  # newest first

    def test_students_are_refused(self):
        student = client_for(make_user('student@thapar.edu'))
        response = self.bulk({'action': 'disable', 'ids': self.ids}, client=student)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Document.objects.filter(status=DocumentStatus.READY).count(), 2)
