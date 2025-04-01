from django.dispatch import Signal

# Sent (after commit) whenever searchable knowledge changes: a document became
# ready, was disabled, edited or deleted. Receivers: the answer cache.
knowledge_changed = Signal()
