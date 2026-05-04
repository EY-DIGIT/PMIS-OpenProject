"""
Meeting repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.meeting import MeetingModel
from ....domain.meetings.meeting import Meeting


class MeetingRepository:
    """Repository for Meeting database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: MeetingModel) -> Meeting:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return Meeting(
            id=model.id,
            project_id=model.project_id,
            title=model.title,
            description=model.description,
            scheduled_at=model.scheduled_at,
            duration_minutes=model.duration_minutes,
            location=model.location,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        project_id: str,
        title: str,
        scheduled_at,
        created_by_id: str,
        description: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        location: Optional[str] = None,
    ) -> Meeting:
        """
        Create a new meeting.

        Args:
            project_id: Project ID
            title: Meeting title
            scheduled_at: Meeting scheduled time
            created_by_id: User ID of creator
            description: Meeting description
            duration_minutes: Meeting duration in minutes
            location: Meeting location

        Returns:
            Created meeting domain model
        """
        meeting_model = MeetingModel(
            project_id=project_id,
            title=title,
            scheduled_at=scheduled_at,
            created_by_id=created_by_id,
            description=description,
            duration_minutes=duration_minutes,
            location=location,
        )

        self.db.add(meeting_model)
        self.db.commit()
        self.db.refresh(meeting_model)

        return self._to_domain(meeting_model)

    def get_by_id(self, meeting_id: int) -> Optional[Meeting]:
        """
        Get meeting by ID.

        Args:
            meeting_id: Meeting ID

        Returns:
            Meeting if found, None otherwise
        """
        model = self.db.query(MeetingModel).filter(MeetingModel.id == meeting_id).first()
        return self._to_domain(model) if model else None

    def list_by_project(self, project_id: str, offset: int = 0, limit: int = 20) -> Tuple[List[Meeting], int]:
        """
        List meetings by project with pagination.

        Args:
            project_id: Project ID
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of meetings, total count)
        """
        total = self.db.query(func.count(MeetingModel.id)).filter(
            MeetingModel.project_id == project_id
        ).scalar()
        models = self.db.query(MeetingModel).filter(
            MeetingModel.project_id == project_id
        ).offset(offset).limit(limit).all()
        meetings = [self._to_domain(m) for m in models]
        return meetings, total

    def exists_by_id(self, meeting_id: int) -> bool:
        """
        Check if meeting exists.

        Args:
            meeting_id: Meeting ID

        Returns:
            True if meeting exists, False otherwise
        """
        return self.db.query(
            self.db.query(MeetingModel).filter(MeetingModel.id == meeting_id).exists()
        ).scalar()

    def exists_in_project(self, meeting_id: int, project_id: str) -> bool:
        """
        Check if meeting exists in project.

        Args:
            meeting_id: Meeting ID
            project_id: Project ID

        Returns:
            True if meeting exists in project, False otherwise
        """
        return self.db.query(
            self.db.query(MeetingModel).filter(
                MeetingModel.id == meeting_id,
                MeetingModel.project_id == project_id
            ).exists()
        ).scalar()

    def update(
        self,
        meeting_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[object] = None,
        duration_minutes: Optional[int] = None,
        location: Optional[str] = None,
    ) -> Optional[Meeting]:
        """
        Update a meeting.

        Args:
            meeting_id: Meeting ID
            title: New title
            description: New description
            scheduled_at: New scheduled time
            duration_minutes: New duration in minutes
            location: New location

        Returns:
            Updated meeting or None if not found
        """
        model = self.db.query(MeetingModel).filter(MeetingModel.id == meeting_id).first()
        if not model:
            return None

        if title is not None:
            model.title = title
        if description is not None:
            model.description = description
        if scheduled_at is not None:
            model.scheduled_at = scheduled_at
        if duration_minutes is not None:
            model.duration_minutes = duration_minutes
        if location is not None:
            model.location = location

        self.db.commit()
        self.db.refresh(model)

        return self._to_domain(model)

    def delete(self, meeting_id: int) -> bool:
        """
        Delete a meeting.

        Args:
            meeting_id: Meeting ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(MeetingModel).filter(MeetingModel.id == meeting_id).first()
        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True
