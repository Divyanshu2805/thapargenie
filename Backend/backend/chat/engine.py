"""The conversation tree.

Messages form a tree through `parent`: a user message's parent is the previous
assistant message, an assistant message's parent is the user message it answers.
Regenerating adds a sibling assistant message; editing a question adds a sibling user
message. `Conversation.current_leaf` marks the branch the student is looking at, and
the "active path" is the chain from the root to that leaf.

Conversations are small (at most 200 messages), so the whole tree is loaded with one
query and walked in Python.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from chat.models import Message

STALE_STREAM = timedelta(minutes=10)


@dataclass
class Tree:
    messages: dict  # id -> Message
    children: dict  # parent id (or None) -> [Message, ...] oldest first

    @classmethod
    def load(cls, conversation):
        rows = list(
            Message.objects.filter(conversation=conversation).order_by('created_at', 'id')
        )
        messages = {message.pk: message for message in rows}
        children = {}
        for message in rows:
            children.setdefault(message.parent_id, []).append(message)
        return cls(messages, children)

    def path_to(self, message_id):
        """Root -> message_id (inclusive)."""
        path = []
        current = self.messages.get(message_id)
        while current is not None:
            path.append(current)
            current = self.messages.get(current.parent_id)
        return list(reversed(path))

    def deepest_from(self, message_id):
        """Follow the newest child from `message_id` down to a leaf."""
        current = self.messages[message_id]
        while self.children.get(current.pk):
            current = self.children[current.pk][-1]
        return current

    def siblings(self, message):
        group = self.children.get(message.parent_id, [])
        return {
            'index': next(i for i, m in enumerate(group) if m.pk == message.pk),
            'count': len(group),
            'ids': [str(m.pk) for m in group],
        }


def active_path(conversation, tree=None):
    tree = tree or Tree.load(conversation)
    if conversation.current_leaf_id and conversation.current_leaf_id in tree.messages:
        return tree.path_to(conversation.current_leaf_id), tree
    # No leaf recorded (e.g. it was deleted): fall back to the newest branch.
    roots = tree.children.get(None, [])
    if not roots:
        return [], tree
    return tree.path_to(tree.deepest_from(roots[-1].pk).pk), tree


def switch_branch(conversation, message_id):
    """Make the branch containing `message_id` current. Returns the new leaf or None."""
    tree = Tree.load(conversation)
    if message_id not in tree.messages:
        return None
    leaf = tree.deepest_from(message_id)
    conversation.current_leaf = leaf
    conversation.save(update_fields=['current_leaf', 'updated_at'])
    return leaf


def history(path):
    """Messages the model should see as prior conversation (oldest first)."""
    usable = []
    for message in path:
        if message.role == Message.Role.USER:
            usable.append({'role': 'user', 'content': message.content})
        elif message.status in (Message.Status.COMPLETE, Message.Status.STOPPED) and \
                message.content:
            usable.append({'role': 'assistant', 'content': message.content})
    return usable


def valid_memory(conversation, path):
    """The rolling summary only applies if it was written for this branch."""
    ids = {message.pk for message in path}
    if conversation.memory_summary and conversation.memory_upto_id in ids:
        return conversation.memory_summary
    return ''


def stale_streams():
    """Answers still marked streaming long after any real stream would have ended."""
    return Message.objects.filter(
        status=Message.Status.STREAMING, updated_at__lt=timezone.now() - STALE_STREAM
    )


def expire_stale_streams(conversation=None, user=None):
    """Mark streams abandoned by a crash or restart as failed."""
    qs = stale_streams()
    if conversation is not None:
        qs = qs.filter(conversation=conversation)
    if user is not None:
        qs = qs.filter(conversation__user=user)
    return qs.update(status=Message.Status.FAILED, error_code='interrupted',
                     updated_at=timezone.now())
