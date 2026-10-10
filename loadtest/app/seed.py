"""Prepare the load-test database and the Auth emulator. Safe to run again.

Refuses to run unless the emulator, the offline AI provider and the load-test database
are selected. It brings the schema up to date, makes sure LT_ACCOUNTS approved students
exist (lt00000@loadtest.example …) with matching emulator accounts, and lifts the daily
limits so the test measures capacity, not quotas.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, '/app')
django.setup()

from api.firebase import get_firebase_app  # noqa: E402
from chat.models import AnswerCache, ChatSettings  # noqa: E402
from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402
from firebase_admin import auth  # noqa: E402
from userauths.models import EligibilityState, User  # noqa: E402

PASSWORD = 'Loadtest-only-password-1!'  # noqa: S105 - emulator accounts only
ACCOUNTS = int(os.getenv('LT_ACCOUNTS', '2000'))
DATABASE = os.getenv('LT_DB', 'thapargenie')


def check_environment():
    database = settings.DATABASES['default']
    problems = []
    if not settings.FIREBASE_AUTH_EMULATOR_HOST:
        problems.append('FIREBASE_AUTH_EMULATOR_HOST is not set')
    if database.get('HOST') not in {'db', 'toxiproxy'} or database.get('NAME') != DATABASE:
        problems.append('the database is not the load-test one')
    if settings.LLM_PROVIDER != 'offline' or settings.EMBED_PROVIDER != 'offline':
        problems.append('the offline AI provider is not selected')
    if problems:
        sys.exit('Refusing to seed: ' + '; '.join(problems) + '.')


def ensure_users():
    emails = [f'lt{i:05d}@loadtest.example' for i in range(ACCOUNTS)]
    known = dict(User.objects.filter(email__in=emails).values_list('email', 'firebase_uid'))
    now = timezone.now()
    for i, email in enumerate(emails):
        if email not in known:
            uid = f'lt{i:05d}'
            User.objects.create_user(
                email=email, firebase_uid=uid, first_name='Load', last_name=f'Test {i}',
                eligibility_state=EligibilityState.APPROVED, eligibility_approved_at=now,
            )
            known[email] = uid
    User.objects.filter(email__in=emails).exclude(
        eligibility_state=EligibilityState.APPROVED
    ).update(eligibility_state=EligibilityState.APPROVED, eligibility_approved_at=now)
    return known


def ensure_emulator_accounts(known):
    app = get_firebase_app()

    def create(item):
        email, uid = item
        try:
            auth.create_user(uid=uid, email=email, email_verified=True, password=PASSWORD,
                             app=app)
            return 1
        except (auth.UidAlreadyExistsError, auth.EmailAlreadyExistsError):
            return 0

    with ThreadPoolExecutor(max_workers=8) as pool:
        return sum(pool.map(create, known.items()))


def main():
    check_environment()
    call_command('migrate', interactive=False, verbosity=0)
    call_command('createcachetable', verbosity=0)
    known = ensure_users()
    created = ensure_emulator_accounts(known)
    chat = ChatSettings.load(fresh=True)
    chat.daily_question_limit = 1_000_000
    chat.global_daily_llm_calls = 1_000_000_000
    chat.rerank_enabled = False  # as in production
    chat.cache_enabled = True
    chat.auto_title_enabled = True
    chat.maintenance_mode = False
    chat.save()
    AnswerCache.objects.all().delete()
    print(f'Ready: {len(known)} students ({created} emulator accounts created), limits lifted.')


if __name__ == '__main__':
    main()
