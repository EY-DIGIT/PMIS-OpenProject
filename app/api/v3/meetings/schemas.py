"""
Meeting API schemas for request/response validation.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


# Meeting Request Schemas
class MeetingCreateRequest(BaseModel):
    """Meeting creation request."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Q1 Planning Meeting",
            "description": "Quarterly planning session",
            "scheduled_at": "2025-03-15T10:00:00Z",
            "duration_minutes": 60,
            "location": "Conference Room A"
        }
    })

    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    description: Optional[str] = Field(None, max_length=5000, description="Meeting description")
    scheduled_at: datetime = Field(..., description="Meeting scheduled time")
    duration_minutes: Optional[int] = Field(None, ge=0, le=10080, description="Duration in minutes")
    location: Optional[str] = Field(None, max_length=255, description="Meeting location")


class MeetingUpdateRequest(BaseModel):
    """Meeting update request."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Q1 Planning Meeting - Updated",
            "location": "Conference Room B"
        }
    })

    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Meeting title")
    description: Optional[str] = Field(None, max_length=5000, description="Meeting description")
    scheduled_at: Optional[datetime] = Field(None, description="Meeting scheduled time")
    duration_minutes: Optional[int] = Field(None, ge=0, le=10080, description="Duration in minutes")
    location: Optional[str] = Field(None, max_length=255, description="Meeting location")


class MeetingListQuery(BaseModel):
    """Meeting list query parameters."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "offset": 1,
            "pageSize": 20
        }
    })

    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=100, description="Items per page")


# Participant Request Schemas
class ParticipantAddRequest(BaseModel):
    """Request to add a participant to a meeting."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": 42
        }
    })

    user_id: str = Field(..., gt=0, description="User ID to add as participant")


# Agenda Item Request Schemas
class AgendaItemCreateRequest(BaseModel):
    """Agenda item creation request."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Budget Review",
            "description": "Review Q1 budget allocation",
            "position": 1,
            "work_package_id": None
        }
    })

    title: str = Field(..., min_length=1, max_length=255, description="Agenda item title")
    description: Optional[str] = Field(None, max_length=5000, description="Agenda item description")
    position: int = Field(..., ge=0, description="Position in the agenda")
    work_package_id: Optional[int] = Field(None, gt=0, description="Optional work package ID")


class AgendaItemUpdateRequest(BaseModel):
    """Agenda item update request."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "position": 2
        }
    })

    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Agenda item title")
    description: Optional[str] = Field(None, max_length=5000, description="Agenda item description")
    position: Optional[int] = Field(None, ge=0, description="Position in the agenda")
    work_package_id: Optional[int] = Field(None, gt=0, description="Optional work package ID")
