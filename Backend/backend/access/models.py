from django.conf import settings
from django.db import models


class SecondFactor(models.Model):
    """A staff member's authenticator app (TOTP). Confirmed once a first code is accepted."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='second_factor'
    )
    # The shared secret, encrypted (access/two_factor.py). Never returned after setup.
    secret = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # The time step of the last accepted code, so a code cannot be used twice.
    last_counter = models.BigIntegerField(default=0)
    # Keyed hashes of the unused backup codes.
    recovery_codes = models.JSONField(default=list, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'access_second_factor'

    def __str__(self):
        return f'Second factor of user {self.user_id}'


class SecondFactorSession(models.Model):
    """One sign-in (a Firebase `auth_time`) that has passed the second factor."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='second_factor_sessions'
    )
    auth_time = models.BigIntegerField()
    verified_at = models.DateTimeField()

    class Meta:
        db_table = 'access_second_factor_session'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'auth_time'), name='second_factor_session_unique'
            ),
        ]

    def __str__(self):
        return f'Second factor session of user {self.user_id}'
