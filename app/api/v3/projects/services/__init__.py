"""
Project services module.
"""
from .create import create_project
from .get import get_project_by_id, get_project_by_identifier
from .list import list_projects
from .update import update_project
from .delete import delete_project
from .upsert import upsert_project
from .publish import publish_project
from .close import close_project
from .suspend import suspend_version
from .version import create_version
from .transitions import (
    transition_to_draft_if_new,
    editable_fields_for,
    PROJECT_STATUS_CHOICES,
    PROJECT_CATEGORY_CHOICES,
)

__all__ = [
    "create_project",
    "get_project_by_id",
    "get_project_by_identifier",
    "list_projects",
    "update_project",
    "delete_project",
    "upsert_project",
    "publish_project",
    "close_project",
    "suspend_version",
    "create_version",
    "transition_to_draft_if_new",
    "editable_fields_for",
    "PROJECT_STATUS_CHOICES",
    "PROJECT_CATEGORY_CHOICES",
]
