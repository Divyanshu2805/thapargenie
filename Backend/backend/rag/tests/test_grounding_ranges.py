from django.test import SimpleTestCase

from rag import grounding
from rag.grounding import range_dates
from rag.tests.test_retrieval import candidate_source

# The shape of the odd-semester calendar table: month and day range in separate columns.
CALENDAR = """
| Week | Month | Dates | Activity |
| Week - 4 | Aug | 24-28 | Teaching |
| Week - 5 | Sept | 31-4 | Teaching (04/09/2026 is a Holiday) |
| Week - 9 | Sept-Oct | 28-3 | MST |
| Week - 14 | Oct / Nov | 2-6 | Teaching |
| Week - 17 | Nov-Dec | 30-4 | Teaching |
| Week - 20 | Dec-Jan | 28-2 | Break |
"""


class RangeDatesTests(SimpleTestCase):
    def test_a_range_that_runs_backwards_crosses_into_the_next_month(self):
        self.assertEqual(range_dates('| Sept | 31-4 |'), {'date:08-31', 'date:09-04'})

    def test_two_months_on_the_row_split_the_range(self):
        self.assertEqual(range_dates('| Sept-Oct | 28-3 |'), {'date:09-28', 'date:10-03'})
        self.assertEqual(range_dates('| Nov-Dec | 30-4 |'), {'date:11-30', 'date:12-04'})

    def test_a_forward_range_in_one_month_stays_in_it(self):
        self.assertEqual(range_dates('| Aug | 24-28 |'), {'date:08-24', 'date:08-28'})

    def test_a_forward_range_over_two_months_accepts_either(self):
        self.assertEqual(range_dates('| Oct / Nov | 2-6 |'),
                         {'date:10-02', 'date:10-06', 'date:11-02', 'date:11-06'})

    def test_the_year_end_wraps(self):
        self.assertEqual(range_dates('| Jan | 28-2 |'), {'date:12-28', 'date:01-02'})

    def test_rows_without_a_month_or_with_a_full_date_give_nothing(self):
        self.assertEqual(range_dates('| Week | 24-28 | Teaching |'), set())
        self.assertEqual(range_dates('Fee due 04-09-2026 in Sept'), set())
        self.assertEqual(range_dates('| Jan Feb Mar | 1-5 |'), set())


class CalendarGroundingTests(SimpleTestCase):
    def sources(self):
        return [candidate_source(1, CALENDAR)]

    def test_month_spanning_weeks_written_in_full_are_supported(self):
        answer = ('Teaching runs 31 Aug – 4 Sep [1], MST is 28 Sep – 3 Oct [1], then 2–6 Nov '
                  'and 30 Nov – 4 Dec [1].')
        check = grounding.check(answer, self.sources())
        self.assertEqual(check.unsupported, [])
        self.assertTrue(check.grounded)

    def test_a_date_the_table_does_not_imply_is_still_flagged(self):
        check = grounding.check('Teaching runs 31 Aug – 5 Sep [1].', self.sources())
        self.assertEqual(check.unsupported, ['date:09-05'])

    def test_the_range_alone_does_not_support_other_days_of_the_month(self):
        check = grounding.check('The break starts on 15 Sep [1].', self.sources())
        self.assertEqual(check.unsupported, ['date:09-15'])

    def test_dates_written_in_full_in_the_source_still_work(self):
        check = grounding.check('The holiday is 4 September 2026 [1].', self.sources())
        self.assertEqual(check.unsupported, [])
