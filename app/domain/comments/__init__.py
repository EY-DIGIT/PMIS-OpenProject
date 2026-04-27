"""Comments + attachments domain entities."""
from .comment import Comment
from .attachment import Attachment

__all__ = ["Comment", "Attachment"]


# Allowed target kinds for both comments and attachments.
# Mirrors the design (which puts the panel on every M/A/T/S node).
TARGET_KINDS = ("milestone", "activity", "task", "subtask")
