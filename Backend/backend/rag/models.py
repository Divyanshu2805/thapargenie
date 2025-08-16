from django.db import models


class EvalTrigger(models.TextChoices):
    NIGHTLY = 'nightly', 'Nightly'
    MANUAL = 'manual', 'Manual'


class EvalRun(models.Model):
    """One scored run of the golden questions. Search quality only."""

    Trigger = EvalTrigger

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    trigger = models.CharField(max_length=10, choices=EvalTrigger.choices,
                               default=EvalTrigger.MANUAL)
    cases = models.PositiveSmallIntegerField()
    recall_at_5 = models.FloatField()
    recall_at_10 = models.FloatField()
    mrr = models.FloatField()
    errors = models.PositiveSmallIntegerField(default=0)
    misses = models.JSONField(default=list, blank=True)
    important_misses = models.JSONField(default=list, blank=True)
    models_used = models.JSONField(default=dict, blank=True)
    llm_calls = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(trigger__in=EvalTrigger.values), name='evalrun_trigger_valid'
            ),
        ]

    def __str__(self):
        return f'eval {self.created_at:%Y-%m-%d} recall@5={self.recall_at_5:.2f}'
