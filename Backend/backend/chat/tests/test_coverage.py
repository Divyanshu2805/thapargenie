"""The "What can I ask?" coverage summary."""

from common.tests.helpers import client_for, make_user
from django.core.cache import cache
from knowledge.models import Document, DocumentStatus
from knowledge.signals import knowledge_changed
from userauths.models import EligibilityState

from chat import coverage
from chat.tests.test_chat import ChatTestCase, add_document

URL = '/api/v1/coverage/'


class CoverageTests(ChatTestCase):
    def setUp(self):
        super().setUp()  # adds one ready fees document
        cache.delete(coverage.CACHE_KEY)
        self.addCleanup(cache.delete, coverage.CACHE_KEY)

    def categories(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_counts_ready_documents_by_category_in_display_order(self):
        calendar = add_document('Calendar', 'Mid sems in October.')
        Document.objects.filter(pk=calendar.pk).update(category='academic_calendar')
        other = add_document('Misc', 'Something else.')
        Document.objects.filter(pk=other.pk).update(category='other')
        queued = add_document('Queued fees', 'Not processed yet.')
        Document.objects.filter(pk=queued.pk).update(status=DocumentStatus.QUEUED)

        data = self.categories()
        self.assertEqual(
            [(c['category'], c['label'], c['documents']) for c in data['categories']],
            [('fees_scholarships', 'Fees & scholarships', 1),
             ('academic_calendar', 'Academic calendar', 1)],
        )
        self.assertEqual(data['total_documents'], 3)  # 'other' counts in the total only
        self.assertNotIn('title', str(data))

    def test_cached_until_the_knowledge_base_changes(self):
        self.assertEqual(self.categories()['total_documents'], 1)
        add_document('Hostel rules', 'Gates close at 10 pm.')
        self.assertEqual(self.categories()['total_documents'], 1)  # still cached
        knowledge_changed.send(sender=Document)
        self.assertEqual(self.categories()['total_documents'], 2)

    def test_needs_an_approved_student(self):
        pending = make_user('pending@thapar.edu', state=EligibilityState.PENDING)
        self.assertEqual(client_for(pending).get(URL).status_code, 403)
        self.assertEqual(self.client_class().get(URL).status_code, 401)
