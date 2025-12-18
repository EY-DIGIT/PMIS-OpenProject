"""
Meeting API schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# Meeting Request Schemas
class MeetingCreateRequest(BaseModel):
    """Meeting creation request."""
    title: str = Field(..., min_length=1, max_length=255, description="Meeting title")
    description: Optional[str] = Field(None, max_length=5000, description="Meeting description")
    scheduled_at: datetime = Field(..., description="Meeting scheduled time")
    duration_minutes: Optional[int] = Field(None, ge=0, le=10080, description="Duration in minutes")
    location: Optional[str] = Field(None, max_length=255, description="Meeting location")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Q1 Planning Meeting",
                "description": "Quarterly planning session",
                "scheduled_at": "2025-03-15T10:00:00Z",
                "duration_minutes": 60,
                "location": "Conference Room A"
            }
        }


class MeetingUpdateRequest(BaseModel):
    """Meeting update request."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Meeting title")
    description: Optional[str] = Field(None, max_length=5000, description="Meeting description")
    scheduled_at: Optional[datetime] = Field(None, description="Meeting scheduled time")
    duration_minutes: Optional[int] = Field(None, ge=0, le=10080, description="Duration in minutes")
    location: Optional[str] = Field(None, max_length=255, description="Meeting location")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Q1 Planning Meeting - Updated",
                "location": "Conference Room B"
            }
        }


class MeetingListQuery(BaseModel):
    """Meeting list query parameters."""
    offset: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of items")

    class Config:
        json_schema_extra = {
            "example": {
                "offset": 0,
                "limit": 20
            }
        }


# Participant Request Schemas
class ParticipantAddRequest(BaseModel):
    """Request to add a participant to a meeting."""
    user_id: int = Field(..., gt=0, description="User ID to add as participant")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 42
            }
        }


# Agenda Item Request Schemas
class AgendaItemCreateRequest(BaseModel):
    """Agenda item creation request."""
    title: str = Field(..., min_length=1, max_length=255, description="Agenda item title")
    description: Optional[str] = Field(None, max_length=5000, description="Agenda item description")
    position: int = Field(..., ge=0, description="Position in the agenda")
    work_package_id: Optional[int] = Field(None, gt=0, description="Optional work package ID")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Budget Review",
                "description": "Review Q1 budget allocation",
                "position": 1,
                "work_package_id": None
            }
        }


class AgendaItemUpdateRequest(BaseModel):
    """Agenda item update request."""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Agenda item title")
    description: Optional[str] = Field(None, max_length=5000, description="Agenda item description")
    position: Optional[int] = Field(None, ge=0, description="Position in the agenda")
    work_package_id: Optional[int] = Field(None, gt=0, description="Optional work package ID")

    class Config:
        json_schema_extra = {
            "example": {
                "position": 2
            }
        }
