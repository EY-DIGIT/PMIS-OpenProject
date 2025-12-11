"""
Meeting domain models for OpenProject Python port.

This module contains the domain models for meetings, including:
- Meeting: Base meeting model
- RecurringMeeting: Recurring meeting series
- ScheduledMeeting: Individual occurrences of recurring meetings
"""

from datetime import datetime, timedelta, date
from enum import Enum
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo


class MeetingState(Enum):
    """Meeting state enumeration."""
    OPEN = 0
    DRAFT = 1
    IN_PROGRESS = 3
    CANCELLED = 4
    CLOSED = 5


class Meeting:
    """
    Meeting domain model representing a single meeting instance.

    Attributes:
        id: Unique identifier
        title: Meeting title
        author_id: ID of the user who created the meeting
        project_id: ID of the associated project
        location: Meeting location (physical or virtual)
        start_time: When the meeting starts
        duration: Duration in hours
        state: Current meeting state
        lock_version: Optimistic locking version
        recurring_meeting_id: Optional ID linking to recurring meeting
        template: Whether this is a template meeting
        notify: Whether to send notifications
        uid: Unique identifier for iCal integration
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    def __init__(
        self,
        id: Optional[int] = None,
        title: str = "",
        author_id: Optional[int] = None,
        project_id: Optional[int] = None,
        location: Optional[str] = None,
        start_time: Optional[datetime] = None,
        duration: float = 1.0,
        state: MeetingState = MeetingState.OPEN,
        lock_version: int = 0,
        recurring_meeting_id: Optional[int] = None,
        template: bool = False,
        notify: bool = True,
        uid: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.title = title
        self.author_id = author_id
        self.project_id = project_id
        self.location = location
        self.start_time = start_time
        self.duration = duration
        self.state = state
        self.lock_version = lock_version
        self.recurring_meeting_id = recurring_meeting_id
        self.template = template
        self.notify = notify
        self.uid = uid
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations (loaded separately)
        self.project = None
        self.author = None
        self.recurring_meeting = None
        self.participants: List[Any] = []
        self.agenda_items: List[Any] = []
        self.sections: List[Any] = []
        self.time_entries: List[Any] = []

    def is_recurring(self) -> bool:
        """Check if this meeting is part of a recurring series."""
        return self.recurring_meeting_id is not None

    def is_template(self) -> bool:
        """Check if this is a template meeting."""
        return self.template

    def is_cancelled(self) -> bool:
        """Check if the meeting is cancelled."""
        return self.state == MeetingState.CANCELLED

    def is_closed(self) -> bool:
        """Check if the meeting is closed."""
        return self.state == MeetingState.CLOSED

    def is_open(self) -> bool:
        """Check if the meeting is open."""
        return self.state == MeetingState.OPEN

    def is_in_progress(self) -> bool:
        """Check if the meeting is in progress."""
        return self.state == MeetingState.IN_PROGRESS

    def get_end_time(self) -> Optional[datetime]:
        """Calculate the meeting end time."""
        if self.start_time and self.duration:
            return self.start_time + timedelta(hours=self.duration)
        return None

    def get_start_month(self) -> Optional[int]:
        """Get the month when the meeting starts."""
        return self.start_time.month if self.start_time else None

    def get_start_year(self) -> Optional[int]:
        """Get the year when the meeting starts."""
        return self.start_time.year if self.start_time else None

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the meeting.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.title or not self.title.strip():
            errors.setdefault("title", []).append("Title is required")

        if not self.project_id:
            errors.setdefault("project_id", []).append("Project is required")

        if self.duration is not None and self.duration <= 0:
            errors.setdefault("duration", []).append("Duration must be greater than 0")

        return errors

    def send_notifications(self) -> bool:
        """Check if notifications should be sent."""
        return self.notify

    def get_agenda_items_sum_duration_in_minutes(self) -> int:
        """Calculate total duration of all agenda items in minutes."""
        total = 0
        for item in self.agenda_items:
            if hasattr(item, 'duration_in_minutes') and item.duration_in_minutes:
                total += item.duration_in_minutes
        return total

    def is_duration_exceeded_by_agenda_items(self) -> bool:
        """Check if agenda items exceed meeting duration."""
        if not self.duration:
            return False

        meeting_duration_minutes = self.duration * 60
        agenda_duration_minutes = self.get_agenda_items_sum_duration_in_minutes()

        return agenda_duration_minutes > meeting_duration_minutes

    def to_dict(self) -> Dict[str, Any]:
        """Convert meeting to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
            "project_id": self.project_id,
            "location": self.location,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "duration": self.duration,
            "state": self.state.name.lower(),
            "lock_version": self.lock_version,
            "recurring_meeting_id": self.recurring_meeting_id,
            "template": self.template,
            "notify": self.notify,
            "uid": self.uid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RecurringMeetingFrequency(Enum):
    """Recurring meeting frequency enumeration."""
    DAILY = 0
    WORKING_DAYS = 1
    WEEKLY = 2


class RecurringMeetingEndAfter(Enum):
    """Recurring meeting end condition enumeration."""
    SPECIFIC_DATE = 0
    ITERATIONS = 1
    NEVER = 3


class RecurringMeeting:
    """
    RecurringMeeting domain model representing a series of recurring meetings.

    Attributes:
        id: Unique identifier
        start_time: First occurrence time
        end_date: When the series ends (optional)
        title: Series title
        frequency: How often meetings occur (daily, weekly, etc.)
        end_after: End condition (date, iterations, or never)
        iterations: Number of iterations (if end_after is ITERATIONS)
        interval: Interval between occurrences
        time_zone: Time zone for the series
        project_id: Associated project ID
        author_id: Creator user ID
        uid: Unique identifier for iCal
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    MAX_ITERATIONS = 1000
    MAX_INTERVAL = 100

    def __init__(
        self,
        id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_date: Optional[date] = None,
        title: str = "",
        frequency: RecurringMeetingFrequency = RecurringMeetingFrequency.WEEKLY,
        end_after: RecurringMeetingEndAfter = RecurringMeetingEndAfter.NEVER,
        iterations: Optional[int] = None,
        interval: int = 1,
        time_zone: str = "UTC",
        project_id: Optional[int] = None,
        author_id: Optional[int] = None,
        uid: Optional[str] = None,
        location: Optional[str] = None,
        duration: float = 1.0,
        notify: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.start_time = start_time
        self.end_date = end_date
        self.title = title
        self.frequency = frequency
        self.end_after = end_after
        self.iterations = iterations
        self.interval = interval
        self.time_zone = time_zone
        self.project_id = project_id
        self.author_id = author_id
        self.uid = uid
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Virtual attributes (passed to template)
        self.location = location
        self.duration = duration
        self.notify = notify

        # Associations
        self.project = None
        self.author = None
        self.meetings: List[Meeting] = []
        self.scheduled_meetings: List['ScheduledMeeting'] = []
        self.template: Optional[Meeting] = None

    def will_end(self) -> bool:
        """Check if the series has an end date."""
        return self.end_after in [
            RecurringMeetingEndAfter.SPECIFIC_DATE,
            RecurringMeetingEndAfter.ITERATIONS
        ]

    def has_ended(self) -> bool:
        """Check if the series has ended."""
        if self.end_after == RecurringMeetingEndAfter.SPECIFIC_DATE:
            return self.end_date and date.today() > self.end_date
        return False

    def send_notifications(self) -> bool:
        """Check if notifications should be sent."""
        return self.notify

    def get_time_zone(self) -> ZoneInfo:
        """Get the time zone object."""
        return ZoneInfo(self.time_zone)

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the recurring meeting.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.title or not self.title.strip():
            errors.setdefault("title", []).append("Title is required")

        if not self.start_time:
            errors.setdefault("start_time", []).append("Start time is required")

        if not self.project_id:
            errors.setdefault("project_id", []).append("Project is required")

        if not self.time_zone:
            errors.setdefault("time_zone", []).append("Time zone is required")

        # End date validation
        if self.end_after == RecurringMeetingEndAfter.SPECIFIC_DATE:
            if not self.end_date:
                errors.setdefault("end_date", []).append(
                    "End date is required when end_after is specific_date"
                )
            elif self.start_time and self.end_date < self.start_time.date():
                errors.setdefault("end_date", []).append(
                    "End date must be after start time"
                )

        # Iterations validation
        if self.end_after == RecurringMeetingEndAfter.ITERATIONS:
            if not self.iterations:
                errors.setdefault("iterations", []).append(
                    "Iterations is required when end_after is iterations"
                )
            elif self.iterations < 1 or self.iterations > self.MAX_ITERATIONS:
                errors.setdefault("iterations", []).append(
                    f"Iterations must be between 1 and {self.MAX_ITERATIONS}"
                )

        # Interval validation
        if self.frequency != RecurringMeetingFrequency.WORKING_DAYS:
            if self.interval < 1 or self.interval > self.MAX_INTERVAL:
                errors.setdefault("interval", []).append(
                    f"Interval must be between 1 and {self.MAX_INTERVAL}"
                )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert recurring meeting to dictionary representation."""
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "title": self.title,
            "frequency": self.frequency.name.lower(),
            "end_after": self.end_after.name.lower(),
            "iterations": self.iterations,
            "interval": self.interval,
            "time_zone": self.time_zone,
            "project_id": self.project_id,
            "author_id": self.author_id,
            "uid": self.uid,
            "location": self.location,
            "duration": self.duration,
            "notify": self.notify,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScheduledMeeting:
    """
    ScheduledMeeting represents an individual occurrence of a recurring meeting.

    Attributes:
        id: Unique identifier
        recurring_meeting_id: Parent recurring meeting ID
        meeting_id: Actual meeting ID (when instantiated)
        start_time: When this occurrence starts
        cancelled: Whether this occurrence is cancelled
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    def __init__(
        self,
        id: Optional[int] = None,
        recurring_meeting_id: Optional[int] = None,
        meeting_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        cancelled: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.recurring_meeting_id = recurring_meeting_id
        self.meeting_id = meeting_id
        self.start_time = start_time
        self.cancelled = cancelled
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations
        self.meeting: Optional[Meeting] = None
        self.recurring_meeting: Optional[RecurringMeeting] = None

    def is_instantiated(self) -> bool:
        """Check if this occurrence has been instantiated as an actual meeting."""
        return self.meeting_id is not None

    def is_cancelled(self) -> bool:
        """Check if this occurrence is cancelled."""
        return self.cancelled

    def is_upcoming(self) -> bool:
        """Check if this occurrence is upcoming."""
        return self.start_time and self.start_time >= datetime.utcnow()

    def is_past(self) -> bool:
        """Check if this occurrence is in the past."""
        return self.start_time and self.start_time < datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert scheduled meeting to dictionary representation."""
        return {
            "id": self.id,
            "recurring_meeting_id": self.recurring_meeting_id,
            "meeting_id": self.meeting_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "cancelled": self.cancelled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
