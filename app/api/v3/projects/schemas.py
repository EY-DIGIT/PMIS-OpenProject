"""
Project API schemas (request/response models).
"""
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .services.transitions import (
    PROJECT_STATUS_CHOICES,
    PROJECT_CATEGORY_CHOICES,
)


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a project.

    ``identifier`` is optional — if omitted, the server generates ``prj{n:03d}``.
    Version identifiers are always server-generated (see POST /versions).
    """
    model_config = ConfigDict(populate_by_name=True)

    identifier: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        pattern="^[a-z0-9_-]+$",
        description="Optional. Server-generates prj{n:03d} when omitted.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: bool = Field(True)
    public: bool = Field(False, alias="isPublic")
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")
    status: str = Field(
        "new",
        description=f"Project status. One of: {', '.join(PROJECT_STATUS_CHOICES)}",
    )
    owner: Optional[str] = Field(
        None, min_length=1, max_length=255,
        description="Owner username (must exist in users table).",
    )
    category: Optional[str] = Field(
        None,
        description=f"Category. One of: {', '.join(PROJECT_CATEGORY_CHOICES)}",
    )
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in PROJECT_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed: {', '.join(PROJECT_STATUS_CHOICES)}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in PROJECT_CATEGORY_CHOICES:
            raise ValueError(
                f"Invalid category '{v}'. Allowed: {', '.join(PROJECT_CATEGORY_CHOICES)}"
            )
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates_in_future(cls, v):
        if v is not None:
            now = datetime.now(timezone.utc)
            check_v = v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
            if check_v <= now:
                raise ValueError("Date must be in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start_date(cls, v, info):
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ProjectUpdateRequest(BaseModel):
    """Request schema for updating a project (PATCH).

    The server filters supplied fields through the editable-field whitelist
    for the project's current state; fields outside the whitelist produce a
    422 invalid_field error. ``actualEndDate`` is accepted here because it is
    a version-only editable field.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: Optional[bool] = None
    public: Optional[bool] = Field(None, alias="isPublic")
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")
    status: Optional[str] = Field(None)
    owner: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None)
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")
    actual_end_date: Optional[datetime] = Field(None, alias="actualEndDate")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in PROJECT_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed: {', '.join(PROJECT_STATUS_CHOICES)}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in PROJECT_CATEGORY_CHOICES:
            raise ValueError(
                f"Invalid category '{v}'. Allowed: {', '.join(PROJECT_CATEGORY_CHOICES)}"
            )
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates_in_future(cls, v):
        if v is not None:
            now = datetime.now(timezone.utc)
            check_v = v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
            if check_v <= now:
                raise ValueError("Date must be in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start_date(cls, v, info):
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ProjectListQuery(BaseModel):
    """Query parameters for listing projects."""

    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=100)
    active: Optional[bool] = None
    public: Optional[bool] = None


class ProjectCloseRequest(BaseModel):
    """Optional body for POST /projects/{id}/close."""
    model_config = ConfigDict(populate_by_name=True)

    reason: Optional[str] = Field(None, max_length=5000)


class ProjectUpsertRequest(BaseModel):
    """Body for PUT /projects/{identifier} (idempotent create-or-update).

    The identifier is taken from the URL path and is NOT accepted in the
    body, so the upsert endpoint cannot be used to rename a project.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: bool = Field(True)
    public: bool = Field(False, alias="isPublic")
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")
    status: str = Field("new")
    owner: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None)
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in PROJECT_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed: {', '.join(PROJECT_STATUS_CHOICES)}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in PROJECT_CATEGORY_CHOICES:
            raise ValueError(
                f"Invalid category '{v}'. Allowed: {', '.join(PROJECT_CATEGORY_CHOICES)}"
            )
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates_in_future(cls, v):
        if v is not None:
            now = datetime.now(timezone.utc)
            check_v = v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)
            if check_v <= now:
                raise ValueError("Date must be in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start_date(cls, v, info):
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v
