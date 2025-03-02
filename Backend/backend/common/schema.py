"""OpenAPI descriptions for views that don't declare serializers themselves.

The auth views in `api/` are left untouched; their request and response shapes are
described here so the generated schema is complete.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension, OpenApiViewExtension
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers


class FirebaseAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'api.authentication.FirebaseAuthentication'
    name = 'FirebaseIdToken'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'Firebase ID token'}


class PreferencesSchema(serializers.Serializer):
    campus = serializers.CharField()
    program = serializers.CharField()
    academic_year = serializers.IntegerField(allow_null=True)


class MeSchema(serializers.Serializer):
    uid = serializers.CharField()
    email = serializers.EmailField()
    email_verified = serializers.BooleanField()
    eligibility_state = serializers.ChoiceField(
        choices=['pending', 'approved', 'denied', 'suspended']
    )
    onboarding_status = serializers.ChoiceField(
        choices=[
            'email_verification_required',
            'approval_pending',
            'ready',
            'access_denied',
            'access_suspended',
        ]
    )
    is_staff = serializers.BooleanField()
    preferences = PreferencesSchema()


class MeViewSchema(OpenApiViewExtension):
    target_class = 'api.views.MeView'

    def view_replacement(self):
        from api.serializers import MeUpdateSerializer

        @extend_schema_view(
            get=extend_schema(responses=MeSchema, tags=['me']),
            patch=extend_schema(request=MeUpdateSerializer, responses=MeSchema, tags=['me']),
        )
        class Described(self.target_class):
            pass

        return Described


class RevokeSessionsViewSchema(OpenApiViewExtension):
    target_class = 'api.views.RevokeSessionsView'

    def view_replacement(self):
        @extend_schema_view(post=extend_schema(request=None, responses={204: None}, tags=['me']))
        class Described(self.target_class):
            pass

        return Described
