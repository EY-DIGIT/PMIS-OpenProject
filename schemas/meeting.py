"""
Pydantic schemas for Meeting API request/response models.

Following OpenProject API v3 HAL+JSON format.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


# Enumerations

class MeetingStateEnum(str, Enum):
    """Meeting state values"""
    open = "open"
    draft = "draft"
    in_progress = "in_progress"
    cancelled = "cancelled"
    closed = "closed"


class RecurringMeetingFrequencyEnum(str, Enum):
    """Recurring meeting frequency values"""
    daily = "daily"
    working_days = "working_days"
    weekly = "weekly"


class RecurringMeetingEndAfterEnum(str, Enum):
    """Recurring meeting end condition values"""
    specific_date = "specific_date"
    iterations = "iterations"
    never = "never"


class ParticipationStatusEnum(str, Enum):
    """Participant status values"""
    needs_action = "needs-action"
    accepted = "accepted"
    declined = "declined"
    tentative = "tentative"
    delegated = "delegated"
    unknown = "unknown"


class AgendaItemTypeEnum(str, Enum):
    """Agenda item type values"""
    simple = "simple"
    work_package = "work_package"


class OutcomeKindEnum(str, Enum):
    """Outcome kind values"""
    information = "information"
    decision = "decision"
    work_package = "work_package"


# HAL+JSON Base schemas

class HALLink(BaseModel):
    """HAL link object"""
    href: str
    title: Optional[str] = None


class HALLinks(BaseModel):
    """HAL _links collection"""
    self: HALLink
    model_config = ConfigDict(extra='allow')


# Meeting Participant schemas

class MeetingParticipantCreate(BaseModel):
    """Meeting participant creation schema"""
    user_id: int = Field(..., description="ID of the user participant")
    invited: bool = Field(default=True, description="Whether the participant is invited")
    participation_status: ParticipationStatusEnum = Field(
        default=ParticipationStatusEnum.needs_action,
        description="Participation status"
    )


class MeetingParticipantUpdate(BaseModel):
    """Meeting participant update schema"""
    invited: Optional[bool] = None
    attended: Optional[bool] = None
    participation_status: Optional[ParticipationStatusEnum] = None


class MeetingParticipantResponse(BaseModel):
    """Meeting participant response schema"""
    _type: str = "MeetingParticipant"
    id: int
    user_id: int
    meeting_id: int
    name: str
    email: str
    invited: bool
    attended: bool
    participation_status: ParticipationStatusEnum
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Meeting Section schemas

class MeetingSectionCreate(BaseModel):
    """Meeting section creation schema"""
    title: Optional[str] = Field(None, max_length=256, description="Section title")
    position: int = Field(default=1, description="Order position")
    backlog: bool = Field(default=False, description="Whether this is the backlog section")


class MeetingSectionUpdate(BaseModel):
    """Meeting section update schema"""
    title: Optional[str] = Field(None, max_length=256)
    position: Optional[int] = None


class MeetingSectionResponse(BaseModel):
    """Meeting section response schema"""
    _type: str = "MeetingSection"
    id: int
    meeting_id: int
    title: str
    position: int
    backlog: bool
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Meeting Agenda Item schemas

class MeetingAgendaItemCreate(BaseModel):
    """Meeting agenda item creation schema"""
    meeting_section_id: Optional[int] = Field(None, description="Section ID (optional, will use default)")
    title: Optional[str] = Field(None, max_length=512, description="Item title (required for simple items)")
    notes: Optional[str] = Field(None, description="Item notes/description")
    work_package_id: Optional[int] = Field(None, description="Work package ID (for work package items)")
    presenter_id: Optional[int] = Field(None, description="Presenter user ID")
    duration_in_minutes: Optional[int] = Field(None, ge=0, le=1440, description="Duration in minutes (0-1440)")
    item_type: AgendaItemTypeEnum = Field(default=AgendaItemTypeEnum.simple, description="Item type")
    position: int = Field(default=1, description="Order position in section")


class MeetingAgendaItemUpdate(BaseModel):
    """Meeting agenda item update schema"""
    meeting_section_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=512)
    notes: Optional[str] = None
    presenter_id: Optional[int] = None
    duration_in_minutes: Optional[int] = Field(None, ge=0, le=1440)
    position: Optional[int] = None


class MeetingAgendaItemResponse(BaseModel):
    """Meeting agenda item response schema"""
    _type: str = "MeetingAgendaItem"
    id: int
    meeting_id: int
    meeting_section_id: int
    author_id: int
    presenter_id: Optional[int]
    work_package_id: Optional[int]
    title: str
    notes: Optional[str]
    position: int
    duration_in_minutes: Optional[int]
    item_type: AgendaItemTypeEnum
    lock_version: int
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Meeting Outcome schemas

class MeetingOutcomeCreate(BaseModel):
    """Meeting outcome creation schema"""
    notes: Optional[str] = Field(None, description="Outcome notes")
    kind: OutcomeKindEnum = Field(default=OutcomeKindEnum.information, description="Outcome kind")
    work_package_id: Optional[int] = Field(None, description="Work package ID (for work package outcomes)")


class MeetingOutcomeUpdate(BaseModel):
    """Meeting outcome update schema"""
    notes: Optional[str] = None
    kind: Optional[OutcomeKindEnum] = None


class MeetingOutcomeResponse(BaseModel):
    """Meeting outcome response schema"""
    _type: str = "MeetingOutcome"
    id: int
    meeting_agenda_item_id: int
    work_package_id: Optional[int]
    author_id: Optional[int]
    notes: Optional[str]
    kind: OutcomeKindEnum
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Meeting schemas

class MeetingCreate(BaseModel):
    """Meeting creation schema"""
    title: str = Field(..., min_length=1, max_length=256, description="Meeting title")
    project_id: int = Field(..., description="Project ID")
    location: Optional[str] = Field(None, max_length=512, description="Meeting location")
    start_time: Optional[datetime] = Field(None, description="Meeting start time")
    duration: float = Field(default=1.0, gt=0, description="Duration in hours")
    state: MeetingStateEnum = Field(default=MeetingStateEnum.open, description="Meeting state")
    notify: bool = Field(default=True, description="Send notifications")
    participants: List[MeetingParticipantCreate] = Field(default_factory=list, description="Meeting participants")
    agenda_items: List[MeetingAgendaItemCreate] = Field(default_factory=list, description="Agenda items")


class MeetingUpdate(BaseModel):
    """Meeting update schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    location: Optional[str] = Field(None, max_length=512)
    start_time: Optional[datetime] = None
    duration: Optional[float] = Field(None, gt=0)
    state: Optional[MeetingStateEnum] = None
    notify: Optional[bool] = None


class MeetingResponse(BaseModel):
    """Meeting response schema (HAL+JSON format)"""
    _type: str = "Meeting"
    id: int
    title: str
    author_id: int
    project_id: int
    location: Optional[str]
    start_time: Optional[datetime]
    duration: float
    state: MeetingStateEnum
    lock_version: int
    recurring_meeting_id: Optional[int]
    template: bool
    notify: bool
    uid: Optional[str]
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Recurring Meeting schemas

class RecurringMeetingCreate(BaseModel):
    """Recurring meeting creation schema"""
    title: str = Field(..., min_length=1, description="Series title")
    project_id: int = Field(..., description="Project ID")
    start_time: datetime = Field(..., description="First occurrence time")
    frequency: RecurringMeetingFrequencyEnum = Field(..., description="Frequency")
    end_after: RecurringMeetingEndAfterEnum = Field(default=RecurringMeetingEndAfterEnum.never, description="End condition")
    end_date: Optional[date] = Field(None, description="End date (if end_after is specific_date)")
    iterations: Optional[int] = Field(None, ge=1, le=1000, description="Number of iterations (if end_after is iterations)")
    interval: int = Field(default=1, ge=1, le=100, description="Interval between occurrences")
    time_zone: str = Field(default="UTC", description="Time zone")
    location: Optional[str] = Field(None, max_length=512, description="Meeting location")
    duration: float = Field(default=1.0, gt=0, description="Duration in hours")
    notify: bool = Field(default=True, description="Send notifications")


class RecurringMeetingUpdate(BaseModel):
    """Recurring meeting update schema"""
    title: Optional[str] = Field(None, min_length=1)
    start_time: Optional[datetime] = None
    frequency: Optional[RecurringMeetingFrequencyEnum] = None
    end_after: Optional[RecurringMeetingEndAfterEnum] = None
    end_date: Optional[date] = None
    iterations: Optional[int] = Field(None, ge=1, le=1000)
    interval: Optional[int] = Field(None, ge=1, le=100)
    time_zone: Optional[str] = None
    location: Optional[str] = Field(None, max_length=512)
    duration: Optional[float] = Field(None, gt=0)
    notify: Optional[bool] = None


class RecurringMeetingResponse(BaseModel):
    """Recurring meeting response schema"""
    _type: str = "RecurringMeeting"
    id: int
    title: str
    author_id: int
    project_id: int
    start_time: datetime
    end_date: Optional[date]
    frequency: RecurringMeetingFrequencyEnum
    end_after: RecurringMeetingEndAfterEnum
    iterations: Optional[int]
    interval: int
    time_zone: str
    location: Optional[str]
    duration: float
    notify: bool
    uid: Optional[str]
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Scheduled Meeting schemas

class ScheduledMeetingResponse(BaseModel):
    """Scheduled meeting response schema"""
    _type: str = "ScheduledMeeting"
    id: int
    recurring_meeting_id: int
    meeting_id: Optional[int]
    start_time: datetime
    cancelled: bool
    created_at: datetime
    updated_at: datetime
    _links: HALLinks

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
