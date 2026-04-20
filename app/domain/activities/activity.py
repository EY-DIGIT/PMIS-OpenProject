"""Activity domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# Enum-style constants for type validation.
ACTIVITY_TYPE_STANDARD = "standard"
ACTIVITY_TYPE_RESOURCE = "resource"
ACTIVITY_TYPE_TRANSACTIONAL = "transactional"
ACTIVITY_TYPES = (
    ACTIVITY_TYPE_STANDARD,
    ACTIVITY_TYPE_RESOURCE,
    ACTIVITY_TYPE_TRANSACTIONAL,
)


@dataclass
class Activity:
    """
    Activity domain entity.

    Activities carry a type (standard/resource/transactional) and optional
    actual dates. When type == 'resource', a matching ActivityResource row
    (1-to-1 on activity_id) carries the resource-specific fields.
    """
    id: int
    project_id: int
    milestone_id: int
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
            "milestone_id": self.milestone_id,
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
