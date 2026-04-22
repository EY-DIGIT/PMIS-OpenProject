"""Subtask API schemas."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....domain.subtasks.subtask import (
    SUBTASK_TYPES,
    SUBTASK_TYPE_RESOURCE,
    RESOURCE_MODES,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)


class ResourcePayload(BaseModel):
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


class SubtaskCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    type: str = Field(...)
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    actual_start_date: Optional[datetime] = Field(None, alias="actualStartDate")
    actual_end_date: Optional[datetime] = Field(None, alias="actualEndDate")
    position: Optional[int] = Field(None, ge=0)
    resource_mode: Optional[str] = Field(None, alias="resourceMode")
    resource_count: Optional[int] = Field(None, ge=1, alias="resourceCount")
    resource: Optional[ResourcePayload] = None
    depends_on: Optional[List[str]] = Field(
        None,
        alias="dependsOn",
        description=(
            "List of subtask UUIDs this subtask depends on. Each target must "
            "live in the same project, and the source's parent task must "
            "already depend on the target's parent task (per "
            "task_dependencies)."
        ),
    )

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in SUBTASK_TYPES:
            raise ValueError(
                "Subtask type must be one of: standard, resource, transactional."
            )
        return v

    @field_validator("resource_mode", mode="before")
    @classmethod
    def _validate_mode(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in RESOURCE_MODES:
            raise ValueError("Resource mode must be either 'count' or 'details'.")
        return v

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v, info):
        s = info.data.get("start_date")
        if s is not None and v < s:
            raise ValueError("End date cannot be before the start date.")
        return v

    @model_validator(mode="after")
    def _resource_shape(self):
        is_resource_type = self.type == SUBTASK_TYPE_RESOURCE
        if not is_resource_type:
            if self.resource_mode is not None:
                raise ValueError(
                    "Resource mode should only be provided when the subtask type is 'resource'."
                )
            if self.resource_count is not None:
                raise ValueError(
                    "Resource count should only be provided when the subtask type is 'resource'."
                )
            if self.resource is not None:
                raise ValueError(
                    "Resource details should only be provided when the subtask type is 'resource'."
                )
            return self
        if self.resource_mode is None:
            raise ValueError(
                "Please choose a resource mode ('count' or 'details') for a resource-type subtask."
            )
        if self.resource_mode == RESOURCE_MODE_COUNT:
            if self.resource_count is None:
                raise ValueError("Resource count is required when resource mode is 'count'.")
            if self.resource is not None:
                raise ValueError("Resource details should be omitted when resource mode is 'count'.")
        else:
            if self.resource is None:
                raise ValueError("Resource details are required when resource mode is 'details'.")
            if self.resource_count is not None:
                raise ValueError("Resource count should be omitted when resource mode is 'details'.")
        return self


class SubtaskUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    type: Optional[str] = None
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")
    actual_start_date: Optional[datetime] = Field(None, alias="actualStartDate")
    actual_end_date: Optional[datetime] = Field(None, alias="actualEndDate")
    position: Optional[int] = Field(None, ge=0)
    resource_mode: Optional[str] = Field(None, alias="resourceMode")
    resource_count: Optional[int] = Field(None, ge=1, alias="resourceCount")
    resource: Optional[ResourcePayload] = None
    depends_on: Optional[List[str]] = Field(None, alias="dependsOn")

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in SUBTASK_TYPES:
            raise ValueError(
                "Subtask type must be one of: standard, resource, transactional."
            )
        return v

    @field_validator("resource_mode", mode="before")
    @classmethod
    def _validate_mode(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in RESOURCE_MODES:
            raise ValueError("Resource mode must be either 'count' or 'details'.")
        return v


class SubtaskListQuery(BaseModel):
    offset: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=100)
    includeDeleted: bool = Field(False)
