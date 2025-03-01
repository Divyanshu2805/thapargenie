from api.staff import StaffGrantDenied, set_staff_access
from django.core.management.base import BaseCommand, CommandError

from userauths.models import User


class Command(BaseCommand):
    help = 'Grant or revoke audited staff access for an already mapped Firebase identity.'

    def add_arguments(self, parser):
        parser.add_argument('--firebase-uid', required=True)
        parser.add_argument('--actor-email', required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--revoke', action='store_true')

    def handle(self, *args, **options):
        actor_email = options['actor_email'].strip().casefold()
        try:
            actor = User.objects.get(email=actor_email)
        except User.DoesNotExist as exc:
            raise CommandError('The actor account does not exist.') from exc
        try:
            target = User.objects.get(firebase_uid=options['firebase_uid'])
        except User.DoesNotExist as exc:
            raise CommandError('The mapped Firebase identity does not exist.') from exc

        try:
            target, changed = set_staff_access(
                actor=actor,
                target=target,
                enabled=not options['revoke'],
                reason=options['reason'],
            )
        except StaffGrantDenied as exc:
            raise CommandError(str(exc)) from exc

        action = 'revoked' if options['revoke'] else 'granted'
        suffix = '' if changed else ' (already in requested state)'
        message = f'Staff access {action}{suffix} for user {target.pk}.'
        self.stdout.write(self.style.SUCCESS(message))
