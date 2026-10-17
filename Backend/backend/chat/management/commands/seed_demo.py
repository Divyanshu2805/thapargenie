"""Create or reset the shared demo account (Demo User) and its sample chats.

    python manage.py seed_demo                 # first run, or to change the password
    python manage.py seed_demo --content-only  # the daily reset: database only

The sample chats are real answers from the live pipeline, so they carry real citations.
A chat counts as a sample while it is still one untouched question and answer; anything
else the previous visitor made is deleted, and a sample that is missing is asked again.
So a day with no changes costs no AI calls.
"""

import os
import uuid

from api.firebase import FirebaseIdentityUnavailable, get_firebase_app
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from firebase_admin import auth
from userauths.demo import (
    DEFAULT_DEMO_PASSWORD,
    DEMO_DISPLAY_NAME,
    DEMO_FIRST_NAME,
    DEMO_LAST_NAME,
    DEMO_PROFILE,
    DEMO_QUESTIONS,
    DEMO_UID,
)
from userauths.models import EligibilityState, User

from chat import answering, background
from chat.models import Conversation, Message, SiteFeedback, UsageDaily


def _ensure_firebase_user(email, password):
    """Create or repair the Firebase account and return its uid."""
    try:
        app = get_firebase_app()
    except FirebaseIdentityUnavailable as exc:
        raise CommandError(f'Firebase is not available: {exc}') from exc
    fields = {
        'email': email, 'email_verified': True, 'password': password,
        'display_name': DEMO_DISPLAY_NAME, 'disabled': False,
    }
    try:
        existing = auth.get_user_by_email(email, app=app)
    except auth.UserNotFoundError:
        try:
            # The account made under an earlier DEMO_ACCOUNT_EMAIL moves to the new one.
            existing = auth.get_user(DEMO_UID, app=app)
        except auth.UserNotFoundError:
            return auth.create_user(uid=DEMO_UID, app=app, **fields).uid
    return auth.update_user(existing.uid, app=app, **fields).uid


def _ensure_local_user(email, uid):
    user = User.objects.filter(email=email).first()
    if user is None and uid:
        user = User.objects.filter(firebase_uid=uid).first()
    if user is None:
        if not uid:
            raise CommandError('The demo account does not exist yet. Run seed_demo without '
                               '--content-only first.')
        user = User(email=email)
    user.email = email
    if uid:
        user.firebase_uid = uid
    user.first_name, user.last_name = DEMO_FIRST_NAME, DEMO_LAST_NAME
    user.is_staff = user.is_superuser = False
    user.is_active = True
    user.eligibility_state = EligibilityState.APPROVED
    user.eligibility_approved_at = user.eligibility_approved_at or timezone.now()
    user.save()
    for name, value in DEMO_PROFILE.items():
        setattr(user.profile, name, value)
    user.profile.save()
    return user


def _is_untouched_sample(conversation):
    """One question and one finished answer, nothing pinned, archived, rated or shared."""
    if conversation.message_count != 2 or conversation.is_pinned or conversation.is_archived:
        return None
    messages = list(conversation.messages.order_by('created_at'))
    if len(messages) != 2 or messages[0].content not in DEMO_QUESTIONS:
        return None
    answer = messages[1]
    if answer.status != Message.Status.COMPLETE or hasattr(answer, 'feedback') \
            or answer.shares.exists():
        return None
    return messages[0].content


def _clear_visitor_changes(user):
    kept = set()
    for conversation in Conversation.objects.owned_by(user):
        question = _is_untouched_sample(conversation)
        if question is None or question in kept:
            conversation.delete()
        else:
            kept.add(question)
    SiteFeedback.objects.filter(user=user).delete()
    return kept


def _ask(user, question):
    conversation = Conversation.objects.create(user=user)
    turn = answering.start_turn(user, conversation, content=question,
                                client_request_id=uuid.uuid4())
    for _event in answering.stream_turn(turn):
        pass
    turn.assistant_message.refresh_from_db()
    if turn.assistant_message.status != Message.Status.COMPLETE:
        conversation.delete()
        raise CommandError(f'The answer to "{question}" failed '
                           f'({turn.assistant_message.error_code or "unknown error"}).')


class Command(BaseCommand):
    help = 'Create or reset the public demo account and its sample chats.'

    def add_arguments(self, parser):
        parser.add_argument('--content-only', action='store_true',
                            help='Only reset the database; leave the Firebase account alone.')

    def handle(self, content_only, **options):
        email = settings.DEMO_ACCOUNT_EMAIL
        if not content_only:
            password = os.getenv('DEMO_ACCOUNT_PASSWORD') or DEFAULT_DEMO_PASSWORD
            uid = _ensure_firebase_user(email, password)
        else:
            uid = None
        user = _ensure_local_user(email, uid)

        with transaction.atomic():
            kept = _clear_visitor_changes(user)
        missing = [question for question in DEMO_QUESTIONS if question not in kept]

        # Jobs that title and summarise a chat run in a background pool in the web process;
        # here they run inline so the command does not exit before they finish.
        background.RUN_INLINE = True
        for question in missing:
            self.stderr.write(f'Asking: {question}')
            _ask(user, question)

        # The seeding questions are not the visitor's: start the day with a full allowance.
        UsageDaily.objects.filter(user=user, day=timezone.localdate()).update(questions=0)
        self.stdout.write(self.style.SUCCESS(
            f'Demo account {email} ready: {len(kept)} sample chats kept, {len(missing)} asked.'))
