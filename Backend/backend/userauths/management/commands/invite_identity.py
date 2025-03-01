from api.models import AuditEvent, AuditOutcome
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from userauths.models import IdentityInvitation, User


class Command(BaseCommand):
    help = 'Create an audited invitation for a normalized email address.'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('--actor-email', required=True)

    def handle(self, *args, **options):
        actor_email = options['actor_email'].strip().casefold()
        invited_email = User.objects.normalize_email(options['email']).strip().casefold()
        try:
            actor = User.objects.get(email=actor_email, is_active=True, is_superuser=True)
        except User.DoesNotExist as exc:
            raise CommandError('The actor must be an active local superuser.') from exc

        try:
            with transaction.atomic():
                invitation = IdentityInvitation.objects.create(
                    email=invited_email,
                    created_by=actor,
                )
                AuditEvent.objects.create(
                    actor=actor,
                    action='identity.invitation_created',
                    resource_type='identity_invitation',
                    resource_id=str(invitation.pk),
                    outcome=AuditOutcome.SUCCEEDED,
                    metadata={'method': 'operator_command'},
                )
        except IntegrityError as exc:
            raise CommandError('An invitation for this email already exists.') from exc

        self.stdout.write(self.style.SUCCESS(f'Created invitation {invitation.pk}.'))
