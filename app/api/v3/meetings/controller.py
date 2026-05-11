"""
Meetings controller - orchestrates requests and responses.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .schemas import (
    MeetingCreateRequest,
    MeetingUpdateRequest,
    MeetingListQuery,
    ParticipantAddRequest,
    AgendaItemCreateRequest,
    AgendaItemUpdateRequest,
)
from .services import (
    create_meeting,
    get_meeting_by_id,
    list_meetings_by_project,
    update_meeting,
    delete_meeting,
)
from .services.participants import (
    add_participant,
    list_participants,
    remove_participant,
)
from .services.agenda import (
    create_agenda_item,
    get_agenda_item,
    list_agenda_items,
    update_agenda_item,
    delete_agenda_item,
)
from app.core.response import (
    format_meeting_response,
    format_meeting_participant_response,
    format_agenda_item_response,
    format_collection_response,
    api_response,
)
from app.core.dependencies import get_current_user_id


class MeetingController:
    """Controller for meeting operations."""

    @staticmethod
    def create_meeting(
        request: Request,
        project_id: str,
        data: MeetingCreateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Create a new meeting.

        Args:
            request: FastAPI request
            project_id: Project ID
            data: Meeting creation data
            db: Database session

        Returns:
            JSONResponse with created meeting
        """
        user_id = get_current_user_id(request)

        result = create_meeting(
            db=db,
            project_id=project_id,
            title=data.title,
            scheduled_at=data.scheduled_at,
            created_by_id=user_id,
            description=data.description,
            duration_minutes=data.duration_minutes,
            location=data.location,
        )

        if not result.success:
            status_code = 400 if result.error_type == "validation_error" else 404 if result.error_type == "not_found" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        meeting = result.data
        return api_response(
            data=format_meeting_response(meeting.to_dict()),
            status=201
        )

    @staticmethod
    def get_meeting(
        request: Request,
        meeting_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get a meeting by ID.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            db: Database session

        Returns:
            JSONResponse with meeting
        """
        result = get_meeting_by_id(db, meeting_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=404 if result.error_type == "not_found" else 500
            )

        meeting = result.data
        return api_response(
            data=format_meeting_response(meeting.to_dict()),
            status=200
        )

    @staticmethod
    def list_meetings(
        request: Request,
        project_id: str,
        query: MeetingListQuery,
        db: Session
    ) -> JSONResponse:
        """
        List meetings in a project.

        Args:
            request: FastAPI request
            project_id: Project ID
            query: Query parameters
            db: Database session

        Returns:
            JSONResponse with paginated meetings
        """
        skip = (query.offset - 1) * query.pageSize
        result = list_meetings_by_project(
            db=db,
            project_id=project_id,
            offset=skip,
            limit=query.pageSize,
        )

        if not result.success:
            return api_response(
                error=result.error,
                status=400 if result.error_type == "validation_error" else 500
            )

        meetings, total = result.data
        formatted_meetings = [format_meeting_response(m.to_dict()) for m in meetings]

        return api_response(
            data=format_collection_response(
                items=formatted_meetings,
                total=total,
                page=query.offset,
                page_size=query.pageSize,
                collection_type="meetings"
            ),
            status=200
        )

    @staticmethod
    def update_meeting(
        request: Request,
        meeting_id: int,
        data: MeetingUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            data: Meeting update data
            db: Database session

        Returns:
            JSONResponse with updated meeting
        """
        result = update_meeting(
            db=db,
            meeting_id=meeting_id,
            title=data.title,
            description=data.description,
            scheduled_at=data.scheduled_at,
            duration_minutes=data.duration_minutes,
            location=data.location,
        )

        if not result.success:
            status_code = 400 if result.error_type == "validation_error" else 404 if result.error_type == "not_found" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        meeting = result.data
        return api_response(
            data=format_meeting_response(meeting.to_dict()),
            status=200
        )

    @staticmethod
    def delete_meeting(
        request: Request,
        meeting_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Delete a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            db: Database session

        Returns:
            JSONResponse with success
        """
        result = delete_meeting(db, meeting_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=404 if result.error_type == "not_found" else 500
            )

        return api_response(
            message="Meeting deleted successfully",
            status=204
        )

    @staticmethod
    def add_participant(
        request: Request,
        meeting_id: int,
        project_id: str,
        data: ParticipantAddRequest,
        db: Session
    ) -> JSONResponse:
        """
        Add a participant to a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            project_id: Project ID
            data: Participant data
            db: Database session

        Returns:
            JSONResponse with created participant
        """
        result = add_participant(
            db=db,
            meeting_id=meeting_id,
            user_id=data.user_id,
            project_id=project_id,
        )

        if not result.success:
            status_code = 403 if result.error_type == "forbidden" else 404 if result.error_type == "not_found" else 409 if result.error_type == "conflict" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        participant = result.data
        return api_response(
            data=format_meeting_participant_response(participant.to_dict()),
            status=201
        )

    @staticmethod
    def list_participants(
        request: Request,
        meeting_id: int,
        db: Session
    ) -> JSONResponse:
        """
        List participants in a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            db: Database session

        Returns:
            JSONResponse with participants
        """
        result = list_participants(db, meeting_id)

        if not result.success:
            status_code = 400 if result.error_type == "validation_error" else 404 if result.error_type == "not_found" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        participants = result.data
        formatted_participants = [format_meeting_participant_response(p.to_dict(), base_url="/api/v3") for p in participants]

        # Build collection HAL for meeting participants
        page = 1
        page_size = len(participants)
        total_pages = 1
        base_collection = f"/api/v3/meetings/{meeting_id}/participants"

        links = {"self": {"href": f"{base_collection}"}}
        # No pagination for participants currently

        collection_payload = {
            "_type": "Collection",
            "_links": links,
            "total": len(participants),
            "count": len(participants),
            "pageSize": page_size,
            "offset": page,
            "_embedded": {"elements": formatted_participants}
        }

        return api_response(
            data=collection_payload,
            status=200
        )

    @staticmethod
    def remove_participant(
        request: Request,
        meeting_id: int,
        user_id: str,
        db: Session
    ) -> JSONResponse:
        """
        Remove a participant from a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            user_id: User ID
            db: Database session

        Returns:
            JSONResponse with success
        """
        result = remove_participant(db, meeting_id, user_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=404 if result.error_type == "not_found" else 500
            )

        return api_response(
            message="Participant removed successfully",
            status=204
        )

    @staticmethod
    def create_agenda_item(
        request: Request,
        meeting_id: int,
        project_id: str,
        data: AgendaItemCreateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Create an agenda item for a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            project_id: Project ID
            data: Agenda item data
            db: Database session

        Returns:
            JSONResponse with created agenda item
        """
        result = create_agenda_item(
            db=db,
            meeting_id=meeting_id,
            project_id=project_id,
            title=data.title,
            position=data.position,
            description=data.description,
            work_package_id=data.work_package_id,
        )

        if not result.success:
            status_code = 400 if result.error_type == "validation_error" else 404 if result.error_type == "not_found" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        agenda_item = result.data
        return api_response(
            data=format_agenda_item_response(agenda_item.to_dict()),
            status=201
        )

    @staticmethod
    def get_agenda_item(
        request: Request,
        agenda_item_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Get an agenda item by ID.

        Args:
            request: FastAPI request
            agenda_item_id: Agenda item ID
            db: Database session

        Returns:
            JSONResponse with agenda item
        """
        result = get_agenda_item(db, agenda_item_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=404 if result.error_type == "not_found" else 500
            )

        agenda_item = result.data
        return api_response(
            data=format_agenda_item_response(agenda_item.to_dict()),
            status=200
        )

    @staticmethod
    def list_agenda_items(
        request: Request,
        meeting_id: int,
        db: Session
    ) -> JSONResponse:
        """
        List agenda items for a meeting.

        Args:
            request: FastAPI request
            meeting_id: Meeting ID
            db: Database session

        Returns:
            JSONResponse with agenda items
        """
        result = list_agenda_items(db, meeting_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=500
            )

        agenda_items = result.data
        formatted_items = [format_agenda_item_response(item.to_dict()) for item in agenda_items]

        return api_response(
            data=format_collection_response(
                items=formatted_items,
                total=len(agenda_items),
                page=1,
                page_size=len(agenda_items),
                collection_type="agenda_items"
            ),
            status=200
        )

    @staticmethod
    def update_agenda_item(
        request: Request,
        agenda_item_id: int,
        data: AgendaItemUpdateRequest,
        db: Session
    ) -> JSONResponse:
        """
        Update an agenda item.

        Args:
            request: FastAPI request
            agenda_item_id: Agenda item ID
            data: Update data
            db: Database session

        Returns:
            JSONResponse with updated agenda item
        """
        result = update_agenda_item(
            db=db,
            agenda_item_id=agenda_item_id,
            title=data.title,
            description=data.description,
            position=data.position,
            work_package_id=data.work_package_id,
        )

        if not result.success:
            status_code = 400 if result.error_type == "validation_error" else 404 if result.error_type == "not_found" else 500
            return api_response(
                error=result.error,
                status=status_code
            )

        agenda_item = result.data
        return api_response(
            data=format_agenda_item_response(agenda_item.to_dict()),
            status=200
        )

    @staticmethod
    def delete_agenda_item(
        request: Request,
        agenda_item_id: int,
        db: Session
    ) -> JSONResponse:
        """
        Delete an agenda item.

        Args:
            request: FastAPI request
            agenda_item_id: Agenda item ID
            db: Database session

        Returns:
            JSONResponse with success
        """
        result = delete_agenda_item(db, agenda_item_id)

        if not result.success:
            return api_response(
                error=result.error,
                status=404 if result.error_type == "not_found" else 500
            )

        return api_response(
            message="Agenda item deleted successfully",
            status=204
        )
