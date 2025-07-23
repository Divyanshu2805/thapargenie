from api.models import AuditEvent
from api.serializers import RejectUnknownFieldsMixin
from django.utils import timezone
from rest_framework import serializers
from userauths.models import IdentityInvitation, User

from access.services import SETTABLE_STATES


class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = IdentityInvitation
        fields = ('id', 'email', 'status', 'expires_at', 'accepted_at', 'created_at')
        read_only_fields = fields

    def get_status(self, invitation) -> str:
        if invitation.accepted_at:
            return 'accepted'
        if not invitation.is_active:
            return 'inactive'
        if invitation.expires_at and invitation.expires_at <= timezone.now():
            return 'expired'
        return 'pending'


class InvitationCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    expires_in_days = serializers.IntegerField(min_value=1, max_value=365, required=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'eligibility_state',
            'eligibility_approved_at', 'is_staff', 'is_active', 'date_joined',
        )
        read_only_fields = fields


class EligibilitySerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    eligibility_state = serializers.ChoiceField(choices=[(s.value, s.label)
                                                         for s in SETTABLE_STATES])
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True)


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source='actor.email', allow_null=True, default=None,
                                         read_only=True)

    class Meta:
        model = AuditEvent
        fields = (
            'id', 'created_at', 'action', 'outcome', 'actor_kind', 'actor_email',
            'resource_type', 'resource_id', 'request_id', 'metadata',
        )
        read_only_fields = fields
