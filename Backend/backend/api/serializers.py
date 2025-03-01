"""Explicit, allowlisted serializers for the public API."""

from rest_framework import serializers


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: ['This field is not allowed.'] for field in sorted(unknown)}
            )
        return super().to_internal_value(data)


class MeUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    campus = serializers.CharField(max_length=100, allow_blank=True, required=False)
    program = serializers.CharField(max_length=120, allow_blank=True, required=False)
    academic_year = serializers.IntegerField(
        min_value=1,
        max_value=12,
        allow_null=True,
        required=False,
    )

    def update(self, instance, validated_data):
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)
        if validated_data:
            instance.save(update_fields=sorted(validated_data))
        return instance

    def create(self, validated_data):
        raise NotImplementedError
