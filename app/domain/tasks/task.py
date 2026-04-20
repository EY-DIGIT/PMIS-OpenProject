"""Task domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


TASK_TYPE_STANDARD = "standard"
TASK_TYPE_RESOURCE = "resource"
TASK_TYPE_TRANSACTIONAL = "transactional"
TASK_TYPES = (TASK_TYPE_STANDARD, TASK_TYPE_RESOURCE, TASK_TYPE_TRANSACTIONAL)


@dataclass
class Task:
    """
    Task domain entity.

    Parent is an Activity. Same shape as Activity but under a different
    parent. Resource sub-entity applies when type == 'resource'.
    """
    id: int
    project_id: int
    activity_id: int
    name: str
    description: Optional[str]
    type: str
    start_date: datetime
    end_date: datetime
    actual_start_date: Optional[datetime]
    actual_end_date: Optional[datetime]
    position: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "activity_id": self.activity_id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "actual_start_date": self.actual_start_date.isoformat() if self.actual_start_date else None,
            "actual_end_date": self.actual_end_date.isoformat() if self.actual_end_date else None,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
