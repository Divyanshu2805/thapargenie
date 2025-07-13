from django.test import SimpleTestCase
from rag.llm.client import LLM
from rag.llm.fake import FakeProvider

from knowledge.ingest import extract as ex
from knowledge.ingest.filetypes import UnsupportedFile, detect
from knowledge.models import SourceType
from knowledge.tests.factories import make_docx, make_pdf, make_xlsx

PROSE = 'The hostel fee for first year students is payable before registration. ' * 4


def fake_llm(provider):
    return LLM(
        chat_provider=provider,
        embed_provider=provider,
        chat_model='chat',
        fast_model='fast',
        embed_model='embed',
        sleep=lambda _s: None,
    )


class DetectTests(SimpleTestCase):
    def test_by_content(self):
        self.assertEqual(detect(make_pdf([['x']]), 'x.docx'), SourceType.PDF)
        self.assertEqual(detect(make_docx(), 'x.pdf'), SourceType.DOCX)
        self.assertEqual(detect(make_xlsx()), SourceType.XLSX)
        self.assertEqual(detect(b'<!DOCTYPE html><html><body>x</body></html>'), SourceType.HTML)
        self.assertEqual(detect(b'a,b\n1,2', 'fees.csv'), SourceType.CSV)
        self.assertEqual(detect('plain text'.encode()), SourceType.TEXT)

    def test_rejects_unknown_binary_and_empty(self):
        for data in (b'', b'\x7fELF\x02\x01\x00\x00', b'PK\x03\x04not-a-zip'):
            with self.subTest(data=data[:8]), self.assertRaises(UnsupportedFile):
                detect(data)


class PdfTests(SimpleTestCase):
    def test_fast_path_adds_page_markers_and_strips_repeated_footer(self):
        pages = [[f'Page body {n}', PROSE, 'Thapar Institute - Confidential'] for n in range(1, 5)]
        result = ex.extract_pdf(make_pdf(pages))
        self.assertFalse(result.used_smart)
        self.assertEqual(result.page_count, 4)
        self.assertIn('[[page 1]]\nPage body 1', result.markdown)
        self.assertIn('[[page 4]]', result.markdown)
        self.assertNotIn('Confidential', result.markdown)

    def test_thin_text_layer_triggers_smart_parsing(self):
        provider = FakeProvider()
        provider.queue('[[page 1]]\n# Fee Structure\n\n| Programme | Fee |\n|---|---|\n| COE | 1 |')
        result = ex.extract_pdf(make_pdf([['scan'], ['scan']]), llm=fake_llm(provider))
        self.assertTrue(result.used_smart)
        self.assertIn('| COE | 1 |', result.markdown)
        self.assertEqual(provider.requests[0][0], 'read_pdf')

    def test_smart_without_llm_is_an_error(self):
        with self.assertRaises(UnsupportedFile):
            ex.extract_pdf(make_pdf([['scan']]))

    def test_forced_fast_ignores_thin_text(self):
        result = ex.extract_pdf(make_pdf([['short']]), mode='fast')
        self.assertIn('short', result.markdown)

    def test_page_limit(self):
        with self.assertRaises(UnsupportedFile):
            ex.extract_pdf(make_pdf([[PROSE]] * 3), max_pages=2)

    def test_smart_windows_cover_every_page(self):
        provider = FakeProvider()
        total = ex.SMART_WINDOW_PAGES + 5
        ex.extract_pdf(make_pdf([['x']] * total), mode='smart', llm=fake_llm(provider))
        self.assertEqual(len(provider.requests), 2)

    def test_garbage_is_rejected(self):
        with self.assertRaises(UnsupportedFile):
            ex.extract_pdf(b'%PDF-1.4 garbage')


class OfficeAndTextTests(SimpleTestCase):
    def test_docx_structure(self):
        result = ex.extract_docx(make_docx())
        self.assertEqual(result.title, 'Hostel Rules')
        self.assertIn('# Hostel Rules', result.markdown)
        self.assertIn('## Timings', result.markdown)
        self.assertIn('- Visitors must sign the register.', result.markdown)
        self.assertIn('| Hall A | 1,20,000 |', result.markdown)

    def test_xlsx_sheets_become_tables(self):
        markdown = ex.extract_xlsx(make_xlsx()).markdown
        self.assertIn('## Fees 2026-27', markdown)
        self.assertIn('| Programme | Tuition \\| per sem |', markdown)
        self.assertIn('| BE ECE | 210000 |', markdown)
        self.assertNotIn('|  |  |', markdown)

    def test_csv_with_semicolons(self):
        markdown = ex.extract_csv('Programme;Seats\nCOE;300\n'.encode()).markdown
        self.assertIn('| COE | 300 |', markdown)

    def test_html_main_content(self):
        html = (
            '<html><head><title>Library</title></head><body><nav>Home | About</nav>'
            '<article><h1>Library timings</h1><p>' + 'The central library opens at 8 am. ' * 10 +
            '</p><table><tr><th>Day</th><th>Hours</th></tr><tr><td>Sunday</td><td>10-5</td></tr>'
            '</table></article></body></html>'
        )
        result = ex.extract_html(html, url='https://www.thapar.edu/library')
        self.assertIn('central library opens', result.markdown)
        self.assertIn('Sunday', result.markdown)

    def test_empty_html_is_rejected(self):
        with self.assertRaises(UnsupportedFile):
            ex.extract_html('<html><body></body></html>')

    def test_markdown_table_helper(self):
        table = ex.markdown_table([['A', 'B'], ['1', None], ['', '']])
        self.assertEqual(table, '| A | B |\n|---|---|\n| 1 |  |')
