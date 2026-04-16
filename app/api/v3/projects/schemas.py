"""
Project API schemas (request/response models).
"""
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Configuration Constants
# Update these lists to add more allowed status or category values
# Path: app/core/constants.py (recommended location for extensibility)
PROJECT_STATUS_CHOICES = ["new", "in_progress", "completed", "on_hold"]
PROJECT_CATEGORY_CHOICES = ["MSAP", "MSIP", "BSP"]


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a project."""
    model_config = ConfigDict(populate_by_name=True)

    identifier: str = Field(..., min_length=1, max_length=255, pattern="^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: bool = Field(True)
    public: bool = Field(False)
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")
    # New fields
    status: str = Field("new", description="Project status. Configure allowed values in app/core/constants.py -> PROJECT_STATUS_CHOICES")
    owner: Optional[str] = Field(None, min_length=1, max_length=255, description="Project owner username. Will be validated against users table.")
    category: Optional[str] = Field(None, description="Project category. Must be one of: MSAP, MSIP, or BSP. Configure in app/core/constants.py -> PROJECT_CATEGORY_CHOICES")
    start_date: Optional[datetime] = Field(None, description="Project start date. Must be in the future.")
    end_date: Optional[datetime] = Field(None, description="Project end date. Must be in the future and after start_date.")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate that status is from the allowed list."""
        if v not in PROJECT_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed values: {', '.join(PROJECT_STATUS_CHOICES)}. "
                f"To add more status values, update PROJECT_STATUS_CHOICES in app/api/v3/projects/schemas.py"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        """Validate that category is from the allowed list."""
        if v is not None and v not in PROJECT_CATEGORY_CHOICES:
            raise ValueError(
                f"Invalid category '{v}'. Allowed values: {', '.join(PROJECT_CATEGORY_CHOICES)}. "
                f"To add more categories, update PROJECT_CATEGORY_CHOICES in app/api/v3/projects/schemas.py"
            )
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates_in_future(cls, v):
        """Validate that dates are in the future."""
        if v is not None:
            # Ensure we're comparing timezone-aware datetimes
            now = datetime.now(timezone.utc)
            if v <= now:
                raise ValueError("Date must be in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start_date(cls, v, info):
        """Validate that end_date is after start_date if both are provided."""
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ProjectUpdateRequest(BaseModel):
    """Request schema for updating a project."""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: Optional[bool] = None
    public: Optional[bool] = None
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")
    # New optional fields
    status: Optional[str] = Field(None, description="Project status. Configure allowed values in app/core/constants.py")
    owner: Optional[str] = Field(None, min_length=1, max_length=255, description="Project owner username")
    category: Optional[str] = Field(None, description="Project category. Must be one of: MSAP, MSIP, or BSP")
    start_date: Optional[datetime] = Field(None, description="Project start date. Must be in the future.")
    end_date: Optional[datetime] = Field(None, description="Project end date. Must be in the future and after start_date.")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate that status is from the allowed list."""
        if v is not None and v not in PROJECT_STATUS_CHOICES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed values: {', '.join(PROJECT_STATUS_CHOICES)}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        """Validate that category is from the allowed list."""
        if v is not None and v not in PROJECT_CATEGORY_CHOICES:
            raise ValueError(
                f"Invalid category '{v}'. Allowed values: {', '.join(PROJECT_CATEGORY_CHOICES)}"
            )
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates_in_future(cls, v):
        """Validate that dates are in the future."""
        if v is not None:
            # Ensure we're comparing timezone-aware datetimes
            now = datetime.now(timezone.utc)
            if v <= now:
                raise ValueError("Date must be in the future")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start_date(cls, v, info):
        """Validate that end_date is after start_date if both are provided."""
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ProjectListQuery(BaseModel):
    """Query parameters for listing projects."""

    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=100, description="Number of items per page")
    active: Optional[bool] = Field(None, description="Filter by active status")
    public: Optional[bool] = Field(None, description="Filter by public status")
