from django.core.management.base import BaseCommand, CommandError
from userauths.models import User

from access import two_factor


class Command(BaseCommand):
    help = (
        "Remove a staff member's two-factor setup (lost phone and no backup codes). "
        'They set it up again at their next sign-in.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--reason', required=True)

    def handle(self, email, reason, **options):
        try:
            user = User.objects.get(email=email.strip().casefold())
        except User.DoesNotExist as exc:
            raise CommandError('No account has that email.') from exc
        if two_factor.reset(user, reason=reason):
            self.stdout.write(self.style.SUCCESS(f'Two-factor reset for user {user.pk}.'))
        else:
            self.stdout.write(f'User {user.pk} had no two-factor setup.')
