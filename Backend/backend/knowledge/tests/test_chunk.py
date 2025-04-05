from common.text import estimate_tokens
from django.test import SimpleTestCase

from knowledge.ingest.chunk import build_chunks, parse_blocks, search_header

SENTENCE = 'Students must complete registration before the first day of classes. '


def table(rows):
    lines = ['| Hostel | Fee |', '|---|---|']
    lines += [f'| Hall {n} | {100000 + n} |' for n in range(rows)]
    return '\n'.join(lines)


class ParseTests(SimpleTestCase):
    def test_headings_pages_and_tables(self):
        markdown = (
            '[[page 3]]\n# Fees\n## Hostel\nIntro text.\n\n'
            + table(2)
            + '\n[[page 4]]\nMore text.'
        )
        blocks = parse_blocks(markdown)
        self.assertEqual([b.kind for b in blocks], ['text', 'table', 'text'])
        self.assertEqual(blocks[0].headings, ('Fees', 'Hostel'))
        self.assertEqual(blocks[0].page_start, 3)
        self.assertEqual(blocks[2].page_start, 4)

    def test_heading_levels_reset(self):
        blocks = parse_blocks('# A\n## B\ntext\n# C\ntext')
        self.assertEqual(blocks[1].headings, ('C',))

    def test_crawler_style_page_markers(self):
        blocks = parse_blocks('[page 7]\nSome text')
        self.assertEqual(blocks[0].page_start, 7)


class BuildChunkTests(SimpleTestCase):
    def test_small_document_is_one_chunk(self):
        chunks = build_chunks('# Library\nOpen 8 am to midnight.')
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading_path, 'Library')
        self.assertNotIn('[[page', chunks[0].content)

    def test_prose_is_packed_near_target_with_overlap(self):
        chunks = build_chunks('\n\n'.join([SENTENCE * 5] * 30), target=200, overlap=40)
        self.assertGreater(len(chunks), 3)
        for chunk in chunks:
            self.assertLessEqual(chunk.token_count, 200 * 1.5)
        tail = chunks[0].content.split('. ')[-1].strip()
        self.assertTrue(chunks[1].content.startswith(tail[:30]))

    def test_no_overlap_across_sections(self):
        markdown = '# A\n' + SENTENCE * 40 + '\n# B\n' + SENTENCE
        chunks = build_chunks(markdown, target=150, overlap=40)
        b_chunks = [c for c in chunks if c.heading_path == 'B']
        self.assertEqual(b_chunks[0].content.strip(), SENTENCE.strip())

    def test_table_is_kept_whole_when_it_fits(self):
        markdown = 'Intro.\n\n' + table(10) + '\n\nOutro.'
        chunks = build_chunks(markdown, target=450)
        tables = [c for c in chunks if c.content.startswith('| Hostel')]
        self.assertEqual(len(tables), 1)
        self.assertIn('Hall 9', tables[0].content)
        self.assertFalse(any('Intro' in c.content and '| Hall' in c.content for c in chunks))

    def test_large_table_repeats_header(self):
        chunks = build_chunks(table(400), target=200, table_max=300)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(chunk.content.startswith('| Hostel | Fee |\n|---|---|'))
        rows = sum(c.content.count('| Hall ') for c in chunks)
        self.assertEqual(rows, 400)

    def test_page_range_spans_pages(self):
        markdown = '[[page 1]]\n' + SENTENCE * 3 + '\n[[page 2]]\n' + SENTENCE * 3
        chunk = build_chunks(markdown, target=1000)[0]
        self.assertEqual((chunk.page_start, chunk.page_end), (1, 2))

    def test_oversized_paragraph_is_split(self):
        chunks = build_chunks(SENTENCE * 200, target=100, overlap=0)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(estimate_tokens(c.content) <= 150 for c in chunks))

    def test_empty_input(self):
        self.assertEqual(build_chunks(''), [])
        self.assertEqual(build_chunks('[[page 1]]\n\n'), [])

    def test_search_header(self):
        header = search_header(
            title='Fee Structure',
            category_label='Fees & scholarships',
            heading_path='Hostel › Boys',
            academic_year='2026-27',
        )
        self.assertEqual(header, 'Fee Structure | Fees & scholarships | Hostel › Boys | 2026-27')
