from django.dispatch import receiver
from knowledge.signals import knowledge_changed

from chat import cache, coverage


@receiver(knowledge_changed)
def clear_answer_cache(**kwargs):
    # Any change to searchable knowledge can make a cached answer wrong.
    cache.clear()
    coverage.forget()
