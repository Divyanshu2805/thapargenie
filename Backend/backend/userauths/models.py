import uuid

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        normalized_email = self.normalize_email(email).strip().casefold()
        user = self.model(email=normalized_email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class EligibilityState(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    APPROVED = 'approved', 'Approved'
    DENIED = 'denied', 'Denied'
    SUSPENDED = 'suspended', 'Suspended'


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    # Staff/synthetic users can exist without a Firebase identity.
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)
    eligibility_state = models.CharField(
        max_length=16,
        choices=EligibilityState.choices,
        default=EligibilityState.PENDING,
        db_index=True,
    )
    eligibility_approved_at = models.DateTimeField(null=True, blank=True)
    firebase_tokens_valid_after = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('email'), name='user_email_case_insensitive_unique'),
            models.CheckConstraint(
                condition=(
                    ~models.Q(eligibility_state=EligibilityState.APPROVED)
                    | models.Q(eligibility_approved_at__isnull=False)
                ),
                name='approved_user_has_approval_time',
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalize_email(self.email).strip().casefold()
        self.firebase_uid = self.firebase_uid or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class IdentityInvitation(models.Model):
    """An operator-created eligibility invitation, never an identity-linking record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='accepted_identity_invitation',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_identity_invitations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('email'), name='invitation_email_ci_unique'),
            models.CheckConstraint(
                condition=(
                    models.Q(accepted_by__isnull=True, accepted_at__isnull=True)
                    | models.Q(accepted_by__isnull=False, accepted_at__isnull=False)
                ),
                name='invitation_acceptance_complete',
            ),
        ]

    def __str__(self):
        return f'Invitation {self.pk}'

    def save(self, *args, **kwargs):
        self.email = User.objects.normalize_email(self.email).strip().casefold()
        super().save(*args, **kwargs)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    campus = models.CharField(max_length=100, blank=True)
    program = models.CharField(max_length=120, blank=True)
    academic_year = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Profile for user {self.user_id}'


@receiver(post_save, sender=User, dispatch_uid='userauths.ensure_profile')
def ensure_user_profile(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    Profile.objects.get_or_create(user=instance)
