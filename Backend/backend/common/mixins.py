"""Abstract model bases and constraint helpers used by every app."""

import uuid

from django.db import models
from django.db.models.functions import Length

# Enables `field__length__lte=` in CHECK constraints.
models.CharField.register_lookup(Length)
models.TextField.register_lookup(Length)


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def choices_check(field, choices, name, *, allow_null=False):
    """CHECK constraint that keeps a TextChoices column inside its enum."""
    condition = models.Q(**{f'{field}__in': choices.values})
    if allow_null:
        condition |= models.Q(**{f'{field}__isnull': True})
    return models.CheckConstraint(condition=condition, name=name)


def max_length_check(field, limit, name):
    """CHECK constraint on text length, for TextFields that have no DB limit."""
    return models.CheckConstraint(
        condition=models.Q(**{f'{field}__length__lte': limit}),
        name=name,
    )

