"""
Work Package domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...shared.datetime import iso_utc


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
    project_id: str
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
            "start_date": iso_utc(self.start_date),
            "end_date": iso_utc(self.end_date),
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
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
