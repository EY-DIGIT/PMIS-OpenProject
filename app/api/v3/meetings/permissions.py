"""
Meetings authorization permissions.
"""
from app.core.rbac import Permission

# Meetings permissions
MEETINGS_VIEW = Permission.MEETINGS_VIEW
MEETINGS_CREATE = Permission.MEETINGS_CREATE
MEETINGS_UPDATE = Permission.MEETINGS_UPDATE
MEETINGS_DELETE = Permission.MEETINGS_DELETE

__all__ = [
    "MEETINGS_VIEW",
    "MEETINGS_CREATE",
    "MEETINGS_UPDATE",
    "MEETINGS_DELETE",
]
