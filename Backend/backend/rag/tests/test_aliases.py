from django.test import SimpleTestCase

from rag.aliases import expand, expansions


class AliasTests(SimpleTestCase):
    def test_programme_abbreviation(self):
        extra = expansions('BE COE fee for 2026-27')
        self.assertIn('Computer Engineering', extra)
        self.assertIn('B.Tech', extra)

    def test_no_partial_word_matches(self):
        # "ME" must not fire inside "mess" or "semester"; "CE" not inside "science".
        self.assertNotIn('Mechanical Engineering', expansions('mess timings this semester'))
        self.assertNotIn('Civil Engineering', expansions('computer science'))

    def test_existing_terms_are_not_repeated(self):
        self.assertNotIn('hostel', expansions('hostel fee'))

    def test_semester_forms(self):
        for text in ('3rd sem', 'third semester', 'Semester III', 'sem 3', 'III semester'):
            with self.subTest(text=text):
                extra = {term.lower() for term in expansions(text)}
                self.assertTrue(
                    {'semester iii', '3rd semester', 'third semester'} - {text.lower()} <= extra
                    | {text.lower()}
                )

    def test_hinglish_style_short_query(self):
        extra = expansions('girls hostel ka mess fee kitna hai')
        self.assertIn('ladies hostel', extra)
        self.assertIn('dining', extra)

    def test_expand_appends_line(self):
        self.assertTrue(expand('COE library').startswith('COE library\n\n'))

    def test_institute_name_is_not_expanded(self):
        # Every document is about TIET; its name must not flood keyword search.
        self.assertEqual(expansions('TIET Thapar library'), [])
        self.assertEqual(expand('nothing to see'), 'nothing to see')
