"""
SQLAlchemy database models for User Service.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float, Date
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

try:
    from .database import Base
except ImportError:
    from database import Base


class DBUser(Base):
    """SQLAlchemy User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(256), unique=True, nullable=False, index=True)
    firstname = Column(String(256))
    lastname = Column(String(256))
    mail = Column(String(256), unique=True, index=True)
    status = Column(Integer, default=1)  # 1=ACTIVE, 2=REGISTERED, 3=INVITED, 4=LOCKED, 5=DELETED
    admin = Column(Boolean, default=False)
    language = Column(String(10), default='en')

    # Authentication
    password_digest = Column(String(256))
    failed_login_count = Column(Integer, default=0)
    last_failed_login_on = Column(DateTime(timezone=True))
    force_password_change = Column(Boolean, default=False)
    last_login_on = Column(DateTime(timezone=True))

    # External auth
    ldap_auth_source_id = Column(Integer, nullable=True)
    uses_external_auth = Column(Boolean, default=False)
    identity_url = Column(String(512), nullable=True)

    # API tokens
    api_key = Column(String(256), unique=True, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    preference = relationship("DBUserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    passwords = relationship("DBUserPassword", back_populates="user", cascade="all, delete-orphan")
    tokens = relationship("DBAPIToken", back_populates="user", cascade="all, delete-orphan")


class DBUserPreference(Base):
    """SQLAlchemy UserPreference model"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    timezone = Column(String(64), default='UTC')
    hide_mail = Column(Boolean, default=True)
    comments_sorting = Column(String(10), default='asc')
    warn_on_leaving_unsaved = Column(Boolean, default=True)
    theme = Column(String(50), default='default')
    notification_settings = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("DBUser", back_populates="preference")


class DBUserPassword(Base):
    """SQLAlchemy UserPassword model"""
    __tablename__ = "user_passwords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("DBUser", back_populates="passwords")


class DBAPIToken(Base):
    """SQLAlchemy API Token model"""
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(256))
    description = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("DBUser", back_populates="tokens")


# Meeting-related models

class DBMeeting(Base):
    """SQLAlchemy Meeting model"""
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, nullable=False)  # Would be ForeignKey("projects.id") when projects table exists
    location = Column(String(512), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, default=1.0)  # Duration in hours
    state = Column(Integer, default=0)  # 0=open, 1=draft, 3=in_progress, 4=cancelled, 5=closed
    lock_version = Column(Integer, default=0)
    recurring_meeting_id = Column(Integer, ForeignKey("recurring_meetings.id"), nullable=True, index=True)
    template = Column(Boolean, default=False)
    notify = Column(Boolean, default=True)
    uid = Column(String(256), unique=True, nullable=True, index=True)  # iCal UID

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    author = relationship("DBUser", foreign_keys=[author_id])
    recurring_meeting = relationship("DBRecurringMeeting", foreign_keys=[recurring_meeting_id], back_populates="meetings")
    participants = relationship("DBMeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    agenda_items = relationship("DBMeetingAgendaItem", back_populates="meeting", cascade="all, delete-orphan")
    sections = relationship("DBMeetingSection", back_populates="meeting", cascade="all, delete-orphan")


class DBRecurringMeeting(Base):
    """SQLAlchemy RecurringMeeting model"""
    __tablename__ = "recurring_meetings"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(Date, nullable=True)
    title = Column(Text, nullable=False)
    frequency = Column(Integer, default=0)  # 0=daily, 1=working_days, 2=weekly
    end_after = Column(Integer, default=0)  # 0=specific_date, 1=iterations, 3=never
    iterations = Column(Integer, nullable=True)
    interval = Column(Integer, default=1)
    time_zone = Column(String(64), nullable=False, default="UTC")
    project_id = Column(Integer, nullable=False)  # Would be ForeignKey("projects.id")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uid = Column(String(256), unique=True, nullable=True, index=True)  # iCal UID

    # Virtual attributes stored for template
    location = Column(String(512), nullable=True)
    duration = Column(Float, default=1.0)
    notify = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    author = relationship("DBUser", foreign_keys=[author_id])
    meetings = relationship("DBMeeting", back_populates="recurring_meeting", cascade="all, delete-orphan")
    scheduled_meetings = relationship("DBScheduledMeeting", back_populates="recurring_meeting", cascade="all, delete-orphan")


class DBScheduledMeeting(Base):
    """SQLAlchemy ScheduledMeeting model - individual occurrences of recurring meetings"""
    __tablename__ = "scheduled_meetings"

    id = Column(Integer, primary_key=True, index=True)
    recurring_meeting_id = Column(Integer, ForeignKey("recurring_meetings.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, unique=True)  # When instantiated
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    cancelled = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    recurring_meeting = relationship("DBRecurringMeeting", back_populates="scheduled_meetings")
    meeting = relationship("DBMeeting")


class DBMeetingParticipant(Base):
    """SQLAlchemy MeetingParticipant model"""
    __tablename__ = "meeting_participants"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    email = Column(String(256), nullable=True)
    name = Column(String(256), nullable=True)
    invited = Column(Boolean, default=False)
    attended = Column(Boolean, default=False)
    participation_status = Column(String(20), default="needs-action")  # needs-action, accepted, declined, tentative, delegated, unknown

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("DBUser")
    meeting = relationship("DBMeeting", back_populates="participants")


class DBMeetingSection(Base):
    """SQLAlchemy MeetingSection model"""
    __tablename__ = "meeting_sections"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    title = Column(String(256), nullable=True)
    position = Column(Integer, default=1)
    backlog = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    meeting = relationship("DBMeeting", back_populates="sections")
    agenda_items = relationship("DBMeetingAgendaItem", back_populates="meeting_section", cascade="all, delete-orphan")


class DBMeetingAgendaItem(Base):
    """SQLAlchemy MeetingAgendaItem model"""
    __tablename__ = "meeting_agenda_items"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    presenter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    meeting_section_id = Column(Integer, ForeignKey("meeting_sections.id"), nullable=False, index=True)
    work_package_id = Column(Integer, nullable=True, index=True)  # Would be ForeignKey("work_packages.id")
    title = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)
    position = Column(Integer, default=1)
    duration_in_minutes = Column(Integer, nullable=True)  # 0-1440 (24 hours)
    item_type = Column(Integer, default=0)  # 0=simple, 1=work_package
    lock_version = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    meeting = relationship("DBMeeting", back_populates="agenda_items")
    meeting_section = relationship("DBMeetingSection", back_populates="agenda_items")
    author = relationship("DBUser", foreign_keys=[author_id])
    presenter = relationship("DBUser", foreign_keys=[presenter_id])
    outcomes = relationship("DBMeetingOutcome", back_populates="meeting_agenda_item", cascade="all, delete-orphan")


class DBMeetingOutcome(Base):
    """SQLAlchemy MeetingOutcome model"""
    __tablename__ = "meeting_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    meeting_agenda_item_id = Column(Integer, ForeignKey("meeting_agenda_items.id"), nullable=False, index=True)
    work_package_id = Column(Integer, nullable=True, index=True)  # Would be ForeignKey("work_packages.id")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    kind = Column(Integer, default=0)  # 0=information, 1=decision, 2=work_package

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    meeting_agenda_item = relationship("DBMeetingAgendaItem", back_populates="outcomes")
    author = relationship("DBUser")
