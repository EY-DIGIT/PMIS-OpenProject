"""
Meeting Agenda Item repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.meeting_agenda_item import MeetingAgendaItemModel
from ....domain.meetings.agenda_item import AgendaItem


class MeetingAgendaItemRepository:
    """Repository for Meeting Agenda Item database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: MeetingAgendaItemModel) -> AgendaItem:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return AgendaItem(
            id=model.id,
            meeting_id=model.meeting_id,
            project_id=model.project_id,
            title=model.title,
            description=model.description,
            position=model.position,
            work_package_id=model.work_package_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        meeting_id: int,
        project_id: str,
        title: str,
        position: int,
        description: Optional[str] = None,
        work_package_id: Optional[int] = None,
    ) -> AgendaItem:
        """
        Create a new agenda item.

        Args:
            meeting_id: Meeting ID
            project_id: Project ID
            title: Agenda item title
            position: Position in the agenda
            description: Agenda item description
            work_package_id: Optional work package ID

        Returns:
            Created agenda item domain model
        """
        agenda_item_model = MeetingAgendaItemModel(
            meeting_id=meeting_id,
            project_id=project_id,
            title=title,
            position=position,
            description=description,
            work_package_id=work_package_id,
        )

        self.db.add(agenda_item_model)
        self.db.commit()
        self.db.refresh(agenda_item_model)

        return self._to_domain(agenda_item_model)

    def get_by_id(self, agenda_item_id: int) -> Optional[AgendaItem]:
        """
        Get agenda item by ID.

        Args:
            agenda_item_id: Agenda item ID

        Returns:
            Agenda item if found, None otherwise
        """
        model = self.db.query(MeetingAgendaItemModel).filter(
            MeetingAgendaItemModel.id == agenda_item_id
        ).first()
        return self._to_domain(model) if model else None

    def list_by_meeting(self, meeting_id: int) -> List[AgendaItem]:
        """
        List all agenda items in a meeting, ordered by position.

        Args:
            meeting_id: Meeting ID

        Returns:
            List of agenda items ordered by position
        """
        models = self.db.query(MeetingAgendaItemModel).filter(
            MeetingAgendaItemModel.meeting_id == meeting_id
        ).order_by(MeetingAgendaItemModel.position).all()
        return [self._to_domain(m) for m in models]

    def exists_by_id(self, agenda_item_id: int) -> bool:
        """
        Check if agenda item exists.

        Args:
            agenda_item_id: Agenda item ID

        Returns:
            True if agenda item exists, False otherwise
        """
        return self.db.query(
            self.db.query(MeetingAgendaItemModel).filter(
                MeetingAgendaItemModel.id == agenda_item_id
            ).exists()
        ).scalar()

    def exists_in_meeting(self, agenda_item_id: int, meeting_id: int) -> bool:
        """
        Check if agenda item exists in meeting.

        Args:
            agenda_item_id: Agenda item ID
            meeting_id: Meeting ID

        Returns:
            True if agenda item exists in meeting, False otherwise
        """
        return self.db.query(
            self.db.query(MeetingAgendaItemModel).filter(
                MeetingAgendaItemModel.id == agenda_item_id,
                MeetingAgendaItemModel.meeting_id == meeting_id
            ).exists()
        ).scalar()

    def update(
        self,
        agenda_item_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        position: Optional[int] = None,
        work_package_id: Optional[int] = None,
    ) -> Optional[AgendaItem]:
        """
        Update an agenda item.

        Args:
            agenda_item_id: Agenda item ID
            title: New title
            description: New description
            position: New position
            work_package_id: New work package ID

        Returns:
            Updated agenda item or None if not found
        """
        model = self.db.query(MeetingAgendaItemModel).filter(
            MeetingAgendaItemModel.id == agenda_item_id
        ).first()
        if not model:
            return None

        if title is not None:
            model.title = title
        if description is not None:
            model.description = description
        if position is not None:
            model.position = position
        if work_package_id is not None:
            model.work_package_id = work_package_id

        self.db.commit()
        self.db.refresh(model)

        return self._to_domain(model)

    def delete(self, agenda_item_id: int) -> bool:
        """
        Delete an agenda item.

        Args:
            agenda_item_id: Agenda item ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(MeetingAgendaItemModel).filter(
            MeetingAgendaItemModel.id == agenda_item_id
        ).first()
        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True
