"""Searching chats by title and message content."""

from django.test import SimpleTestCase

from chat.models import Conversation
from chat.serializers import search_snippet
from chat.tests.test_chat import ChatTestCase, approved_user, client_for

URL = '/api/v1/conversations/'


class SnippetTests(SimpleTestCase):
    def test_window_around_the_first_match(self):
        text = 'word ' * 30 + 'The boys hostel fee is Rs 1,20,000 per year.' + ' more' * 30
        snippet = search_snippet(text, 'HOSTEL FEE', width=20)
        self.assertTrue(snippet.startswith('…') and snippet.endswith('…'))
        self.assertIn('boys hostel fee is', snippet)
        self.assertLessEqual(len(snippet), 20 * 2 + len('hostel fee') + 2)

    def test_short_text_and_collapsed_whitespace(self):
        self.assertEqual(search_snippet('Mess\n\n fee  is extra', 'fee'), 'Mess fee is extra')


class ConversationSearchTests(ChatTestCase):
    def search(self, q, client=None, **params):
        response = (client or self.client).get(URL, {'q': q, **params})
        self.assertEqual(response.status_code, 200)
        return response.data['results']

    def test_finds_words_in_answers_and_questions_with_a_snippet(self):
        conversation = self.conversation()
        self.answered(conversation)  # asks "boys hostel fee?", answers "... Rs 1,20,000 ..."

        [hit] = self.search('1,20,000')
        self.assertEqual(hit['id'], str(conversation.pk))
        self.assertEqual(hit['match']['role'], 'assistant')
        self.assertIn('Rs 1,20,000 per year', hit['match']['snippet'])

        [hit] = self.search('boys hostel')  # in both: the newest message wins
        self.assertEqual(hit['match']['role'], 'assistant')
        self.assertEqual(self.search('not mentioned anywhere'), [])

    def test_title_only_matches_have_no_snippet(self):
        Conversation.objects.create(user=self.user, title='Mess menu questions')
        [hit] = self.search('mess menu')
        self.assertIsNone(hit['match'])

    def test_never_searches_another_students_chats(self):
        other = approved_user('other@thapar.edu')
        mine = self.conversation()
        self.answered(mine)
        theirs = self.conversation(user=other)
        self.answered(theirs, client=client_for(other))
        self.assertEqual([hit['id'] for hit in self.search('hostel')], [str(mine.pk)])

    def test_short_queries_are_ignored_and_the_archive_toggle_applies(self):
        conversation = self.conversation()
        self.answered(conversation)
        Conversation.objects.create(user=self.user, title='Other chat')
        self.assertEqual(len(self.search('h')), 2)  # 1 character: no search, no `match`
        self.assertNotIn('match', self.search('h')[0])

        Conversation.objects.filter(pk=conversation.pk).update(is_archived=True)
        self.assertEqual(self.search('hostel'), [])
        self.assertEqual([hit['id'] for hit in self.search('hostel', archived='true')],
                         [str(conversation.pk)])
