"""The shared demo account: a public sign-in so anyone can look around without registering.

Its email and password are published on the sign-in page and in the README on purpose.
It is a normal approved student (never staff) that the API locks out of the few actions
that would hurt the next visitor, and `seed_demo` puts it back every day.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

# Firebase uids cannot change, so this keeps the uid the account was first made with.
DEMO_UID = 'demo-aarav-sharma'
DEMO_FIRST_NAME = 'Demo'
DEMO_LAST_NAME = 'User'
DEMO_DISPLAY_NAME = f'{DEMO_FIRST_NAME} {DEMO_LAST_NAME}'
DEMO_PROFILE = {'campus': 'Patiala', 'program': 'B.E. Computer Engineering', 'academic_year': 1}
# Public, like the email. Easy to type; Firebase needs at least 6 characters.
DEFAULT_DEMO_PASSWORD = 'demo1234'  # noqa: S105

# The questions the demo account starts the day with, oldest first.
DEMO_QUESTIONS = (
    'What is the first-year hostel fee?',
    'When do the hostel gates close?',
    'How much attendance do I need?',
    'How does the placement process work?',
    'When are the mid-semester exams?',
    'What scholarships are available?',
    'Who is the vice chancellor?',
)


class DemoAccountLocked(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This is the shared demo account, so this is turned off for it.'
    default_code = 'demo_account_locked'


def is_demo(user):
    # The uid keeps the account locked while it is moved to a new DEMO_ACCOUNT_EMAIL.
    return bool(user) and (getattr(user, 'email', '') == settings.DEMO_ACCOUNT_EMAIL
                           or getattr(user, 'firebase_uid', None) == DEMO_UID)


def forbid_demo(user):
    """Raise for the demo account; call at the top of actions that would hurt other visitors."""
    if is_demo(user):
        raise DemoAccountLocked()
