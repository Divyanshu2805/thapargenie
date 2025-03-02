from django.test import SimpleTestCase

from common.text import estimate_tokens, normalize_text, truncate


class TextTests(SimpleTestCase):
    def test_normalize_collapses_spaces_and_blank_lines(self):
        raw = 'Hostel   Fee\r\n\r\n\r\n\r\nBoys\t\tHostel\x00 '
        self.assertEqual(normalize_text(raw), 'Hostel Fee\n\nBoys Hostel')

    def test_normalize_applies_nfkc(self):
        self.assertEqual(normalize_text('ﬁnal ２０２６'), 'final 2026')

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(''), 0)
        self.assertEqual(estimate_tokens('abcd'), 1)
        self.assertEqual(estimate_tokens('a' * 400), 100)

    def test_truncate_keeps_short_text(self):
        self.assertEqual(truncate('short', 10), 'short')

    def test_truncate_cuts_on_word_boundary(self):
        result = truncate('What is the hostel fee for first year students', 20)
        self.assertLessEqual(len(result), 20)
        self.assertEqual(result, 'What is the hostel…')
