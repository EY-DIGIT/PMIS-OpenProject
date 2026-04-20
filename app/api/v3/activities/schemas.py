"""Activity API schemas (with nested resource)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....domain.activities.activity import ACTIVITY_TYPES, ACTIVITY_TYPE_RESOURCE


class ResourcePayload(BaseModel):
    """Resource fields (inline for create; partial for update)."""
    model_config = ConfigDict(populate_by_name=True)

    resource_name: str = Field(..., min_length=1, max_length=255, alias="resourceName")
    onboard_date: Optional[datetime] = Field(None, alias="onboardDate")
    actual_onboard_date: Optional[datetime] = Field(None, alias="actualOnboardDate")
    offboard_date: Optional[datetime] = Field(None, alias="offboardDate")
    actual_offboard_date: Optional[datetime] = Field(None, alias="actualOffboardDate")
    position: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    job_role: Optional[str] = Field(None, max_length=255, alias="jobRole")
    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: Optional[Decimal] = Field(None, ge=0, le=99, alias="experienceYears")


class ActivityCreateRequest(BaseModel):
    """POST /milestones/{milestone_id}/activities."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    type: str = Field(...)
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    actual_start_date: Optional[datetime] = Field(None, alias="actualStartDate")
    actual_end_date: Optional[datetime] = Field(None, alias="actualEndDate")
    position: Optional[int] = Field(None, ge=0)
    resource: Optional[ResourcePayload] = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v):
        if v not in ACTIVITY_TYPES:
            raise ValueError(
                "Activity type must be one of: Standard, Resource, or Transactional."
            )
        return v

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v, info):
        s = info.data.get("start_date")
        if s is not None and v < s:
            raise ValueError("End date cannot be before the start date.")
        return v

    @model_validator(mode="after")
    def _resource_presence(self):
        if self.type == ACTIVITY_TYPE_RESOURCE and self.resource is None:
            raise ValueError(
                "Resource details are required when the activity type is 'Resource'."
            )
        if self.type != ACTIVITY_TYPE_RESOURCE and self.resource is not None:
            raise ValueError(
                "Resource details should only be provided when the activity type is 'Resource'."
            )
        return self


class ActivityUpdateRequest(BaseModel):
    """PATCH /activities/{id}. Partial; handles type transitions."""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    type: Optional[str] = None
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")
    actual_start_date: Optional[datetime] = Field(None, alias="actualStartDate")
    actual_end_date: Optional[datetime] = Field(None, alias="actualEndDate")
    position: Optional[int] = Field(None, ge=0)
    resource: Optional[ResourcePayload] = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v):
        if v is not None and v not in ACTIVITY_TYPES:
            raise ValueError(
                "Activity type must be one of: Standard, Resource, or Transactional."
            )
        return v


class ActivityListQuery(BaseModel):
    offset: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=100)
    includeDeleted: bool = Field(False)
