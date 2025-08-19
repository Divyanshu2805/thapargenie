"""Seed a local database and the Firebase Auth emulator for the browser tests.

Refuses to run anywhere but a local end-to-end setup: the Firebase emulator must be on,
the database must be local, and the offline AI provider and memory storage must be
selected. It recreates its own users and resets the knowledge base to one document, so
every run starts from the same state.
"""

import os
import time
from datetime import timedelta

from api.firebase import get_firebase_app
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from firebase_admin import auth
from knowledge import services
from knowledge.models import Document, DocumentStatus
from rag.analysis import current_session
from userauths.models import EligibilityState, User

PASSWORD = 'E2e-only-password-1!'  # noqa: S105 - emulator accounts only
ACCOUNTS = (
    # email, uid, first name, staff
    ('e2e-student@example.com', 'e2e-student', 'Student', False),
    ('e2e-admin@example.com', 'e2e-admin', 'Admin', True),
)
DOCUMENT_TITLE = 'Hostel fee structure'
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


def _database_host():
    return settings.DATABASES['default'].get('HOST')


def _check_environment():
    problems = []
    if os.getenv('APP_ENV', 'local').strip().lower() == 'production':
        problems.append('APP_ENV is production')
    if not settings.FIREBASE_AUTH_EMULATOR_HOST:
        problems.append('FIREBASE_AUTH_EMULATOR_HOST is not set')
    if _database_host() not in LOCAL_HOSTS:
        problems.append('the database is not local')
    if settings.LLM_PROVIDER != 'offline' or settings.EMBED_PROVIDER != 'offline':
        problems.append('the offline AI provider is not selected')
    if settings.STORAGE_BACKEND != 'memory':
        problems.append('memory storage is not selected')
    if problems:
        raise CommandError('Refusing to seed: ' + '; '.join(problems) + '.')


class Command(BaseCommand):
    help = 'Create the end-to-end test accounts (Firebase emulator) and a searchable document.'

    def handle(self, **options):
        _check_environment()
        app = get_firebase_app()
        users = {}
        for email, uid, first_name, staff in ACCOUNTS:
            try:
                auth.delete_user(uid, app=app)
            except auth.UserNotFoundError:
                pass
            auth.create_user(uid=uid, email=email, email_verified=True, password=PASSWORD,
                             display_name=f'E2E {first_name}', app=app)
            User.objects.filter(Q(email=email) | Q(firebase_uid=uid)).delete()
            users[uid] = User.objects.create_user(
                email=email, firebase_uid=uid, first_name=first_name, last_name='E2E',
                eligibility_state=EligibilityState.APPROVED,
                eligibility_approved_at=timezone.now(), is_staff=staff,
            )

        today = timezone.localdate()
        # Every run starts from the same knowledge base (this is a throwaway database).
        Document.objects.all().delete()
        document = services.create_from_text(
            title=DOCUMENT_TITLE,
            text=('The boys hostel fee for the current session is Rs 1,20,000 per year, '
                  'payable in two instalments. The girls hostel fee is Rs 1,10,000 per year. '
                  'The mess fee is charged separately at Rs 45,000 per year.'),
            meta={'category': 'fees_scholarships', 'academic_year': current_session(today),
                  'effective_date': today - timedelta(days=30)},
            user=users['e2e-admin'],
        )
        # Processing runs on the background worker; wait for it here.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            document.refresh_from_db()
            if document.status in (DocumentStatus.READY, DocumentStatus.FAILED):
                break
            time.sleep(0.2)
        if document.status != DocumentStatus.READY:
            raise CommandError(f'The seed document did not process: {document.status} '
                               f'{document.error}')
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(ACCOUNTS)} emulator accounts and "{DOCUMENT_TITLE}".'))
