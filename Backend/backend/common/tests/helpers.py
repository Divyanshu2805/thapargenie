import time

from api.identity import FirebaseIdentity
from django.utils import timezone
from rest_framework.test import APIClient
from userauths.models import EligibilityState, User


def make_user(email, *, staff=False, state=EligibilityState.APPROVED):
    return User.objects.create_user(
        email=email,
        firebase_uid=f'uid-{email}',
        is_staff=staff,
        eligibility_state=state,
        eligibility_approved_at=timezone.now() if state == EligibilityState.APPROVED else None,
    )


def client_for(user, *, signed_in_seconds_ago=0, email_verified=True):
    client = APIClient()
    identity = FirebaseIdentity(
        user.firebase_uid, user.email, email_verified,
        int(time.time()) - signed_in_seconds_ago, {},
    )
    client.force_authenticate(user=user, token=identity)
    return client
