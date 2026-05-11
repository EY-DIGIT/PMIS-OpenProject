"""
Work Package request/response schemas.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


WORK_PACKAGE_STATUS_CHOICES = ["new", "in_progress", "resolved", "closed", "on_hold"]
WORK_PACKAGE_PRIORITY_CHOICES = ["low", "normal", "high", "urgent"]


class WorkPackageCreateRequest(BaseModel):
    """Request to create a work package."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Implement user authentication",
                "description": "Add JWT authentication to the API",
                "typeId": 1,
                "assigneeId": 5,
                "status": "new",
                "priority": "high",
                "doneRatio": 0
            }
        }
    )

    subject: str = Field(..., min_length=1, max_length=255, description="Work package title")
    description: Optional[str] = Field(None, max_length=5000, description="Work package description")
    parentId: Optional[int] = Field(None, description="Parent work package ID (for subtasks)")
    typeId: Optional[int] = Field(None, description="Work package type ID (auto-resolved from hierarchy depth if omitted)")
    assigneeId: Optional[int] = Field(None, description="Assigned user ID")
    status: str = Field(default="new", description="Status: new, in_progress, resolved, closed, on_hold")
    priority: str = Field(default="normal", description="Priority: low, normal, high, urgent")
    doneRatio: int = Field(default=0, ge=0, le=100, description="Completion percentage")
    startDate: Optional[datetime] = Field(None, description="Start date (required for milestones/activities)")
    endDate: Optional[datetime] = Field(None, description="End date (required for milestones/activities)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in WORK_PACKAGE_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed values: {', '.join(WORK_PACKAGE_STATUS_CHOICES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v not in WORK_PACKAGE_PRIORITY_CHOICES:
            raise ValueError(
                f"Invalid priority '{v}'. Allowed values: {', '.join(WORK_PACKAGE_PRIORITY_CHOICES)}"
            )
        return v

    @field_validator("endDate")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if v is not None and "startDate" in info.data and info.data["startDate"] is not None:
            # Inclusive: endDate == startDate is allowed.
            if v < info.data["startDate"]:
                raise ValueError("endDate cannot be before startDate")
        return v


class WorkPackageUpdateRequest(BaseModel):
    """Request to update a work package."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Updated title",
                "status": "in_progress",
                "doneRatio": 50
            }
        }
    )

    subject: Optional[str] = Field(None, min_length=1, max_length=255, description="Work package title")
    description: Optional[str] = Field(None, max_length=5000, description="Work package description")
    assigneeId: Optional[int] = Field(None, description="Assigned user ID")
    status: Optional[str] = Field(None, description="Status: new, in_progress, resolved, closed, on_hold")
    priority: Optional[str] = Field(None, description="Priority: low, normal, high, urgent")
    doneRatio: Optional[int] = Field(None, ge=0, le=100, description="Completion percentage")
    typeId: Optional[int] = Field(None, description="Work package type ID")
    startDate: Optional[datetime] = Field(None, description="Start date")
    endDate: Optional[datetime] = Field(None, description="End date")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in WORK_PACKAGE_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed values: {', '.join(WORK_PACKAGE_STATUS_CHOICES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v is not None and v not in WORK_PACKAGE_PRIORITY_CHOICES:
            raise ValueError(
                f"Invalid priority '{v}'. Allowed values: {', '.join(WORK_PACKAGE_PRIORITY_CHOICES)}"
            )
        return v


class WorkPackageListQuery(BaseModel):
    """Query parameters for listing work packages."""
    offset: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(default=20, ge=1, le=100, description="Items per page")
    parentId: Optional[int] = Field(None, description="Filter by parent work package ID")
    type: Optional[str] = Field(None, description="Filter by type internal_name (e.g. milestone, activity, task)")
