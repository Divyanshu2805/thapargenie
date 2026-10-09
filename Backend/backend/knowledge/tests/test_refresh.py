from io import StringIO
from unittest import mock

from api.models import AuditEvent
from common.safe_http import FetchError, FetchResult
from django.core.management import call_command

from knowledge import services
from knowledge.ingest.pipeline import process_document
from knowledge.models import Document, DocumentStatus
from knowledge.refresh import refresh_web_pages
from knowledge.tests.test_pipeline import KnowledgeTestCase

URL = 'https://www.thapar.edu/hostels'
FIRST = ('The boys hostel fee is Rs 1,20,000 per year and includes the mess charges for '
         'both semesters of the academic session.')
SECOND = FIRST.replace('1,20,000', '1,35,000')


def page(body, nonce='a'):
    # The nonce stands for markup that changes on every request (scripts, nonces).
    html = (f'<html><head><title>Hostels</title><script>var t="{nonce}"</script></head>'
            f'<body><article><h1>Hostels</h1><p>{body}</p></article></body></html>')
    return FetchResult(url=URL, content_type='text/html', content=html.encode())


class RefreshTests(KnowledgeTestCase):
    def setUp(self):
        super().setUp()
        self.live = page(FIRST)
        patcher = mock.patch('knowledge.ingest.pipeline.fetch', side_effect=self.fetch)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.document = self.web_page(URL, 'Hostels')

    def web_page(self, url, title):
        with mock.patch('knowledge.services.validate_url'), \
                self.captureOnCommitCallbacks(execute=False):
            document = services.create_from_url(
                url=url, meta={'title': title, 'category': 'hostel_campus_life'},
                user=self.admin,
            )
        document = process_document(document.pk)
        self.assertEqual(document.status, DocumentStatus.READY)
        return document

    def fetch(self, url, **kwargs):
        if isinstance(self.live, Exception):
            raise self.live
        return self.live

    def refresh(self, **kwargs):
        return refresh_web_pages(fetcher=self.fetch, sleep=lambda _s: None, **kwargs)

    def test_an_unchanged_page_is_left_alone_even_if_its_markup_differs(self):
        self.live = page(FIRST, nonce='b')
        embeds = len(self.fake.embed_calls)
        stats = self.refresh()
        self.assertEqual((stats.checked, stats.unchanged, stats.changed), (1, 1, 0))
        self.assertEqual(len(self.fake.embed_calls), embeds)
        self.document.refresh_from_db()
        self.assertTrue(self.document.metadata['page_checked_at'])

    def test_a_changed_page_is_read_again(self):
        self.live = page(SECOND)
        stats = self.refresh()
        self.assertEqual((stats.changed, stats.changed_titles), (1, ['Hostels']))
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, DocumentStatus.READY)
        self.assertIn('1,35,000', self.document.chunks.get().content)
        event = AuditEvent.objects.get(action='document.refreshed')
        self.assertEqual(event.resource_id, str(self.document.pk))
        self.assertIsNone(event.actor)
        # The new text is now the baseline.
        self.assertEqual(self.refresh().unchanged, 1)

    def test_dry_run_reports_and_changes_nothing(self):
        self.live = page(SECOND)
        before = dict(self.document.metadata)
        stats = self.refresh(dry_run=True)
        self.assertEqual(stats.changed, 1)
        self.document.refresh_from_db()
        self.assertEqual(self.document.metadata, before)
        self.assertIn('1,20,000', self.document.chunks.get().content)
        self.assertFalse(AuditEvent.objects.filter(action='document.refreshed').exists())

    def test_a_page_that_cannot_be_fetched_keeps_its_passages(self):
        self.live = FetchError('Upstream returned HTTP 503.')
        stats = self.refresh()
        self.assertEqual((stats.failed, stats.changed), (1, 0))
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, DocumentStatus.READY)
        self.assertIn('503', self.document.metadata['page_check_error'])
        self.assertEqual(self.document.chunks.count(), 1)

    def test_a_page_stored_before_fingerprints_only_gets_one_recorded(self):
        metadata = {k: v for k, v in self.document.metadata.items() if k != 'page_fingerprint'}
        Document.objects.filter(pk=self.document.pk).update(metadata=metadata)
        self.live = page(SECOND)
        stats = self.refresh()
        self.assertEqual((stats.first_seen, stats.changed), (1, 0))
        self.assertEqual(self.refresh().unchanged, 1)

    def test_pages_are_spaced_out_and_other_documents_are_ignored(self):
        self.text_document()
        self.web_page(URL + '/girls', 'Girls hostels')
        waits = []
        stats = refresh_web_pages(fetcher=self.fetch, sleep=waits.append, delay=2)
        self.assertEqual(stats.checked, 2)
        self.assertEqual(waits, [2])

    def test_command_reports(self):
        self.live = page(SECOND)
        out = StringIO()
        with mock.patch('knowledge.refresh.fetch', side_effect=self.fetch):
            call_command('refresh_web_pages', '--dry-run', '--delay', '0', stdout=out)
        self.assertIn('changed: Hostels', out.getvalue())
        self.assertIn('1 changed (would be re-read)', out.getvalue())
