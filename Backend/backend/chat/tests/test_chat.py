import hashlib
import json
import time
import uuid

from api.identity import FirebaseIdentity
from django.test import TestCase
from django.utils import timezone
from knowledge.ingest.chunk import ChunkDraft
from knowledge.ingest.pipeline import prepare_chunks
from knowledge.models import Chunk, Document, DocumentStatus, SourceType
from knowledge.storage import MemoryStorage, use_storage
from rag.llm import LLMError, use_provider
from rag.llm.fake import FakeProvider, hashed_embedding
from rest_framework.test import APIClient
from userauths.models import EligibilityState, User

from chat import background, engine, memory
from chat.models import (
    ChatSettings,
    Conversation,
    Feedback,
    Message,
    MessageSource,
    UsageDaily,
)

ANALYSIS = {
    'intent': 'college_query', 'standalone_query': 'boys hostel fee 2026-27',
    'alternate_queries': [], 'keywords': 'hostel fee', 'categories': [],
    'academic_year': '', 'needs_current': True, 'language': 'english',
}
ANSWER = 'The boys hostel fee is Rs 1,20,000 per year [1].'


def approved_user(email):
    return User.objects.create_user(
        email=email,
        firebase_uid=f'uid-{email}',
        eligibility_state=EligibilityState.APPROVED,
        eligibility_approved_at=timezone.now(),
    )


def client_for(user):
    client = APIClient()
    identity = FirebaseIdentity(user.firebase_uid, user.email, True, int(time.time()), {})
    client.force_authenticate(user=user, token=identity)
    return client


def add_document(title, text, url='https://www.thapar.edu/fees'):
    document = Document.objects.create(
        title=title, source_type=SourceType.TEXT, source_url=url,
        content_hash=hashlib.sha256(title.encode()).hexdigest(),
        category='fees_scholarships', status=DocumentStatus.READY,
    )
    chunks = prepare_chunks(document, [ChunkDraft(text, '', 1, 1)])
    for chunk in chunks:
        chunk.embedding = hashed_embedding(chunk.search_text, 768)
        chunk.is_searchable = True
    Chunk.objects.bulk_create(chunks)
    return document


def read_events(response):
    events = []
    for frame in b''.join(response.streaming_content).decode().split('\n\n'):
        if frame.startswith('event: '):
            name, data = frame.split('\n', 1)
            events.append((name[7:], json.loads(data[6:])))
    return events


class ChatTestCase(TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        use_provider(self.fake)
        self.addCleanup(use_provider, None)
        background.RUN_INLINE = True
        self.addCleanup(setattr, background, 'RUN_INLINE', False)
        ChatSettings.objects.update_or_create(
            pk=1, defaults={'auto_title_enabled': False}
        )
        ChatSettings.forget()
        self.addCleanup(ChatSettings.forget)
        self.user = approved_user('student@thapar.edu')
        self.client = client_for(self.user)
        self.document = add_document('Hostel fees', 'Boys hostel fee is Rs 1,20,000 per year.')

    def conversation(self, user=None):
        return Conversation.objects.create(user=user or self.user)

    def ask(self, conversation, content='boys hostel fee?', key=None, client=None, **extra):
        return (client or self.client).post(
            f'/api/v1/conversations/{conversation.pk}/messages/',
            {'content': content, 'client_request_id': str(key or uuid.uuid4()), **extra},
            format='json',
        )

    def answered(self, conversation, answer=ANSWER, **kwargs):
        self.fake.queue(ANALYSIS, answer)
        response = self.ask(conversation, **kwargs)
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        return read_events(response)


class AskTests(ChatTestCase):
    def test_full_turn_streams_and_persists(self):
        conversation = self.conversation()
        events = self.answered(conversation)
        names = [name for name, _ in events]
        self.assertEqual(names[0], 'meta')
        self.assertIn('sources', names)
        self.assertEqual(names[-1], 'done')
        self.assertEqual(''.join(d['text'] for n, d in events if n == 'delta'), ANSWER)

        user_message, assistant = Message.objects.order_by('created_at')
        self.assertEqual(user_message.content, 'boys hostel fee?')
        self.assertEqual(assistant.parent, user_message)
        self.assertEqual(assistant.status, Message.Status.COMPLETE)
        self.assertEqual(assistant.answer_type, Message.AnswerType.ANSWERED)
        source = MessageSource.objects.get(message=assistant)
        self.assertTrue(source.cited)
        self.assertEqual(source.url, 'https://www.thapar.edu/fees')

        conversation.refresh_from_db()
        self.assertEqual(conversation.current_leaf, assistant)
        self.assertEqual(conversation.message_count, 2)
        self.assertEqual(conversation.title, 'boys hostel fee?')
        usage = UsageDaily.objects.get(user=self.user)
        self.assertEqual((usage.questions, usage.answers), (1, 1))
        self.assertGreater(usage.llm_calls, 0)

        done = events[-1][1]
        self.assertEqual(done['message']['sources'][0]['position'], 1)
        self.assertEqual(done['remaining_today'], 39)

    def test_idempotent_retry_replays_without_new_messages(self):
        conversation = self.conversation()
        key = uuid.uuid4()
        self.answered(conversation, key=key)
        calls = len(self.fake.requests)
        events = read_events(self.ask(conversation, key=key))
        self.assertEqual([n for n, _ in events], ['meta', 'sources', 'delta', 'done'])
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(len(self.fake.requests), calls)

    def test_follow_up_sees_history(self):
        conversation = self.conversation()
        self.answered(conversation)
        self.answered(conversation, content='and for girls?')
        analysis_prompt = self.fake.requests[-2].prompt
        self.assertIn('Student: boys hostel fee?', analysis_prompt)
        answer_request = self.fake.requests[-1]
        self.assertEqual(answer_request.history[0].content, 'boys hostel fee?')
        path, _ = engine.active_path(Conversation.objects.get(pk=conversation.pk))
        self.assertEqual(len(path), 4)

    def test_validation(self):
        conversation = self.conversation()
        for body in ({'content': '   ', 'client_request_id': str(uuid.uuid4())},
                     {'content': 'x' * 2001, 'client_request_id': str(uuid.uuid4())},
                     {'content': 'ok', 'client_request_id': 'nope'},
                     {'content': 'ok', 'client_request_id': str(uuid.uuid4()), 'role': 'x'}):
            with self.subTest(body=body):
                response = self.client.post(
                    f'/api/v1/conversations/{conversation.pk}/messages/', body, format='json'
                )
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.exists())

    def test_llm_failure_keeps_question_and_marks_failed(self):
        conversation = self.conversation()
        self.fake.queue(ANALYSIS, LLMError('boom'))
        events = read_events(self.ask(conversation))
        self.assertEqual(events[-1][0], 'error')
        self.assertEqual(events[-1][1]['code'], 'llm_unavailable')
        user_message, assistant = Message.objects.order_by('created_at')
        self.assertEqual(user_message.content, 'boys hostel fee?')
        self.assertEqual(assistant.status, Message.Status.FAILED)
        self.assertEqual(assistant.error_code, 'llm_unavailable')

    def test_client_disconnect_saves_partial_answer(self):
        conversation = self.conversation()
        self.fake.queue(ANALYSIS, 'The boys hostel fee is Rs 1,20,000 per year [1].')
        response = self.ask(conversation)
        stream = iter(response.streaming_content)
        received = b''
        while b'event: delta' not in received:
            received += next(stream)
        # What WSGI does when the browser goes away: close the body iterator. (Not
        # response.close(), which in tests also closes the DB connection.)
        response._iterator.close()
        assistant = Message.objects.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.status, Message.Status.STOPPED)
        self.assertTrue(assistant.content.startswith('The'))

    def test_greeting_is_answered_without_sources(self):
        conversation = self.conversation()
        self.fake.queue({**ANALYSIS, 'intent': 'greeting'})
        read_events(self.ask(conversation, content='hi'))
        assistant = Message.objects.get(role=Message.Role.ASSISTANT)
        self.assertEqual(assistant.answer_type, Message.AnswerType.SMALLTALK)
        self.assertFalse(assistant.sources.exists())


class LimitTests(ChatTestCase):
    def test_daily_quota(self):
        ChatSettings.objects.filter(pk=1).update(daily_question_limit=1)
        ChatSettings.forget()
        conversation = self.conversation()
        self.answered(conversation)
        response = self.ask(conversation)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['error']['code'], 'daily_quota_exceeded')

    def test_staff_are_exempt_from_daily_quota(self):
        ChatSettings.objects.filter(pk=1).update(daily_question_limit=0)
        ChatSettings.forget()
        self.user.is_staff = True
        self.user.save()
        self.answered(self.conversation())

    def test_global_budget_breaker(self):
        UsageDaily.objects.create(user=None, day=timezone.localdate(), llm_calls=10**6)
        response = self.ask(self.conversation())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error']['code'], 'service_busy')

    def test_one_stream_per_user(self):
        other = self.conversation()
        Message.objects.create(conversation=other, role=Message.Role.ASSISTANT,
                               status=Message.Status.STREAMING)
        response = self.ask(self.conversation())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'conversation_busy')

    def test_stale_stream_does_not_block_forever(self):
        other = self.conversation()
        stale = Message.objects.create(conversation=other, role=Message.Role.ASSISTANT,
                                       status=Message.Status.STREAMING)
        Message.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - engine.STALE_STREAM * 2
        )
        self.answered(self.conversation())  # not blocked
        self.client.get(f'/api/v1/conversations/{other.pk}/messages/')
        stale.refresh_from_db()
        self.assertEqual(stale.status, Message.Status.FAILED)
        self.assertEqual(stale.error_code, 'interrupted')

    def test_full_conversation(self):
        conversation = self.conversation()
        Conversation.objects.filter(pk=conversation.pk).update(message_count=199)
        response = self.ask(conversation)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'conversation_full')


class BranchTests(ChatTestCase):
    def messages(self, conversation):
        response = self.client.get(f'/api/v1/conversations/{conversation.pk}/messages/')
        self.assertEqual(response.status_code, 200)
        return response.data['messages']

    def test_regenerate_creates_sibling_and_switches(self):
        conversation = self.conversation()
        self.answered(conversation)
        first = Message.objects.get(role=Message.Role.ASSISTANT)
        self.fake.queue(ANALYSIS, 'Second try: Rs 1,20,000 [1].')
        response = self.client.post(f'/api/v1/messages/{first.pk}/regenerate/',
                                    {'client_request_id': str(uuid.uuid4())}, format='json')
        read_events(response)
        messages = self.messages(conversation)
        self.assertEqual(len(messages), 2)
        self.assertTrue(messages[1]['content'].startswith('Second try'))
        self.assertEqual(messages[1]['siblings']['count'], 2)
        self.assertEqual(messages[1]['siblings']['index'], 1)

        self.client.patch(f'/api/v1/conversations/{conversation.pk}/',
                          {'current_leaf_id': str(first.pk)}, format='json')
        self.assertEqual(self.messages(conversation)[1]['id'], str(first.pk))

    def test_edit_creates_new_branch_and_old_one_survives(self):
        conversation = self.conversation()
        self.answered(conversation)
        self.answered(conversation, content='and mess fee?')
        second_question = Message.objects.get(content='and mess fee?')
        self.answered(conversation, content='and girls hostel fee?',
                      edit_of=str(second_question.pk))
        path = self.messages(conversation)
        self.assertEqual([m['content'] for m in path if m['role'] == 'user'],
                         ['boys hostel fee?', 'and girls hostel fee?'])
        self.assertEqual(path[2]['siblings']['count'], 2)
        # Switching to the old question restores its answer.
        self.client.patch(f'/api/v1/conversations/{conversation.pk}/',
                          {'current_leaf_id': str(second_question.pk)}, format='json')
        path = self.messages(conversation)
        self.assertEqual(path[2]['content'], 'and mess fee?')
        self.assertEqual(len(path), 4)

    def test_cannot_regenerate_a_question(self):
        conversation = self.conversation()
        self.answered(conversation)
        question = Message.objects.get(role=Message.Role.USER)
        response = self.client.post(f'/api/v1/messages/{question.pk}/regenerate/',
                                    {'client_request_id': str(uuid.uuid4())}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'invalid_parent')


class OwnershipTests(ChatTestCase):
    def test_other_users_see_nothing(self):
        conversation = self.conversation()
        self.answered(conversation)
        assistant = Message.objects.get(role=Message.Role.ASSISTANT)
        source = MessageSource.objects.get()
        intruder = client_for(approved_user('other@thapar.edu'))
        checks = [
            intruder.get(f'/api/v1/conversations/{conversation.pk}/'),
            intruder.get(f'/api/v1/conversations/{conversation.pk}/messages/'),
            intruder.patch(f'/api/v1/conversations/{conversation.pk}/', {'title': 'x'},
                           format='json'),
            intruder.delete(f'/api/v1/conversations/{conversation.pk}/'),
            intruder.post(f'/api/v1/messages/{assistant.pk}/regenerate/',
                          {'client_request_id': str(uuid.uuid4())}, format='json'),
            intruder.put(f'/api/v1/messages/{assistant.pk}/feedback/', {'rating': -1},
                         format='json'),
            intruder.get(f'/api/v1/sources/{source.pk}/open/'),
            self.ask(conversation, client=intruder),
        ]
        self.assertEqual([r.status_code for r in checks], [404] * len(checks))
        self.assertEqual(intruder.get('/api/v1/conversations/').data['results'], [])
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_unapproved_and_anonymous_are_refused(self):
        pending = User.objects.create_user(email='pending@thapar.edu', firebase_uid='p')
        self.assertEqual(client_for(pending).get('/api/v1/conversations/').status_code, 403)
        self.assertIn(APIClient().get('/api/v1/conversations/').status_code, (401, 403))


class ConversationApiTests(ChatTestCase):
    def test_list_filters_and_search(self):
        a = Conversation.objects.create(user=self.user, title='Hostel fees', is_pinned=True)
        Conversation.objects.create(user=self.user, title='Library hours')
        Conversation.objects.create(user=self.user, title='Old', is_archived=True)
        titles = lambda qs: [c['title'] for c in self.client.get(  # noqa: E731
            f'/api/v1/conversations/{qs}').data['results']]
        self.assertEqual(sorted(titles('')), ['Hostel fees', 'Library hours'])
        self.assertEqual(titles('?pinned=true'), ['Hostel fees'])
        self.assertEqual(titles('?archived=true'), ['Old'])
        self.assertEqual(titles('?q=libr'), ['Library hours'])
        self.assertEqual(str(a.pk), self.client.get('/api/v1/conversations/?pinned=true')
                         .data['results'][0]['id'])

    def test_create_rename_delete(self):
        created = self.client.post('/api/v1/conversations/', {}, format='json').data
        response = self.client.patch(f'/api/v1/conversations/{created["id"]}/',
                                     {'title': '  My   fees  ', 'is_pinned': True}, format='json')
        self.assertEqual(response.data['title'], 'My fees')
        conversation = Conversation.objects.get(pk=created['id'])
        self.assertEqual(conversation.title_source, Conversation.TitleSource.USER)
        self.assertEqual(self.client.delete(f'/api/v1/conversations/{created["id"]}/')
                         .status_code, 204)
        self.assertFalse(Conversation.objects.exists())

    def test_delete_all_only_touches_own(self):
        self.conversation()
        other = approved_user('b@thapar.edu')
        Conversation.objects.create(user=other)
        self.assertEqual(self.client.delete('/api/v1/conversations/').status_code, 204)
        self.assertEqual(list(Conversation.objects.values_list('user', flat=True)), [other.pk])

    def test_app_config_and_export(self):
        conversation = self.conversation()
        self.answered(conversation)
        config = self.client.get('/api/v1/app-config/').data
        self.assertEqual(config['remaining_today'], 39)
        self.assertTrue(config['starter_questions'])
        export = self.client.get('/api/v1/me/export/')
        self.assertIn('attachment', export['Content-Disposition'])
        data = json.loads(export.content)
        self.assertEqual(len(data['conversations'][0]['messages']), 2)


class FeedbackAndSourceTests(ChatTestCase):
    def test_feedback_upsert_and_delete(self):
        self.answered(self.conversation())
        assistant = Message.objects.get(role=Message.Role.ASSISTANT)
        url = f'/api/v1/messages/{assistant.pk}/feedback/'
        self.assertEqual(self.client.put(url, {'rating': 1}, format='json').status_code, 200)
        response = self.client.put(url, {'rating': -1, 'reason': 'outdated',
                                         'comment': 'Old fee'}, format='json')
        self.assertEqual(response.data['reason'], 'outdated')
        self.assertEqual(Feedback.objects.get().rating, -1)
        self.assertEqual(self.client.put(url, {'rating': 5}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Feedback.objects.exists())

    def test_open_source_url_or_signed_file(self):
        self.answered(self.conversation())
        source = MessageSource.objects.get()
        self.assertEqual(self.client.get(f'/api/v1/sources/{source.pk}/open/').data['url'],
                         'https://www.thapar.edu/fees')
        storage = MemoryStorage()
        use_storage(storage)
        self.addCleanup(use_storage, None)
        Document.objects.filter(pk=self.document.pk).update(storage_path='documents/x.pdf')
        MessageSource.objects.filter(pk=source.pk).update(url='')
        url = self.client.get(f'/api/v1/sources/{source.pk}/open/').data['url']
        self.assertTrue(url.startswith('memory://documents/x.pdf'))


class MemoryAndTitleTests(ChatTestCase):
    def test_auto_title(self):
        ChatSettings.objects.filter(pk=1).update(auto_title_enabled=True)
        ChatSettings.forget()
        conversation = self.conversation()
        self.fake.queue(ANALYSIS, ANSWER, 'Boys hostel fee')
        read_events(self.ask(conversation))
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, 'Boys hostel fee')

    def test_user_title_is_never_overwritten(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Mine', title_source=Conversation.TitleSource.USER
        )
        memory.make_title(conversation.pk, 'anything')
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, 'Mine')
