"""
Work Package domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WorkPackage:
    """
    Work Package domain entity.

    Represents a task, issue, or subtask in OpenProject.
    This is the business model, separate from database concerns.
    """

    id: int
    subject: str
    description: Optional[str]
    project_id: int
    assignee_id: Optional[int]
    status: str
    priority: str
    done_ratio: int
    type_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    parent_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_dict(self) -> dict:
        """
        Convert work package to dictionary.

        Returns:
            Dictionary representation of work package
        """
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "type_id": self.type_id,
            "assignee_id": self.assignee_id,
            "status": self.status,
            "priority": self.priority,
            "done_ratio": self.done_ratio,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_subtask(self) -> bool:
        """
        Check if this work package is a subtask.

        Returns:
            True if this work package has a parent
        """
        return self.parent_id is not None

    def is_completed(self) -> bool:
        """
        Check if work package is completed.

        Returns:
            True if done_ratio is 100
        """
        return self.done_ratio >= 100
