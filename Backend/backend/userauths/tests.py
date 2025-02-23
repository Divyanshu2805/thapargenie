from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from userauths.models import EligibilityState, Profile, User


class TestUserIdentityFoundation(TestCase):
    def test_create_user_normalizes_email_and_creates_optional_profile(self):
        user = User.objects.create_user(email='  Student@Example.COM  ')

        self.assertEqual(user.email, 'student@example.com')
        self.assertIsNone(user.username)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.eligibility_state, EligibilityState.PENDING)
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_case_insensitive_email_is_unique(self):
        User.objects.create_user(email='student@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email='STUDENT@example.com')

    def test_nullable_firebase_uid_allows_unmapped_users_but_uid_is_unique(self):
        first = User.objects.create_user(email='first@example.com')
        User.objects.create_user(email='second@example.com')
        first.firebase_uid = 'firebase-uid-1'
        first.save(update_fields=['firebase_uid'])

        duplicate = User.objects.create_user(email='third@example.com')
        duplicate.firebase_uid = 'firebase-uid-1'
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save(update_fields=['firebase_uid'])

    def test_approved_user_requires_approval_timestamp(self):
        user = User.objects.create_user(email='approved@example.com')
        user.eligibility_state = EligibilityState.APPROVED
        with self.assertRaises(IntegrityError), transaction.atomic():
            user.save(update_fields=['eligibility_state'])

        user.eligibility_approved_at = timezone.now()
        user.save(update_fields=['eligibility_state', 'eligibility_approved_at'])

    def test_missing_profile_is_recreated_safely(self):
        user = User.objects.create_user(email='profile@example.com')
        user.profile.delete()
        user.first_name = 'Synthetic'
        user.save(update_fields=['first_name'])
        self.assertTrue(Profile.objects.filter(user=user).exists())
