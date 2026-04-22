"""Activity API schemas (with nested resource)."""
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....domain.activities.activity import (
    ACTIVITY_STATUS_CHOICES,
    ACTIVITY_STATUS_DEFAULT,
    ACTIVITY_TYPES,
    ACTIVITY_TYPE_RESOURCE,
    ACTIVITY_TYPE_STANDARD,
    RESOURCE_MODES,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)
from ....domain.resource_types.resource_type import DIVISION_CHOICES, DIVISION_OTHERS


class ResourcePayload(BaseModel):
    """Resource fields (inline for create; partial for update).

    Classification additions:
      - ``typeOfResourceId`` references ``/resource_types``. Required on
        *create* when the parent activity is type='resource' in details mode.
      - ``division`` is one of DIVISION_CHOICES. When ``division == 'others'``,
        ``divisionOther`` must be a non-empty string. Otherwise it must be
        omitted / null.
    """
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
    type_of_resource_id: Optional[str] = Field(
        None,
        alias="typeOfResourceId",
        description="UUID of a row in /resource_types (required on create).",
    )
    division: Optional[str] = Field(
        None,
        description=f"One of: {', '.join(DIVISION_CHOICES)}",
    )
    division_other: Optional[str] = Field(
        None,
        alias="divisionOther",
        max_length=255,
        description=f"Required (non-empty) when division == '{DIVISION_OTHERS}'.",
    )

    @field_validator("division", mode="before")
    @classmethod
    def _validate_division(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in DIVISION_CHOICES:
            raise ValueError(
                f"Division must be one of: {', '.join(DIVISION_CHOICES)}."
            )
        return v

    @model_validator(mode="after")
    def _validate_division_other(self):
        # Enforce the 'others + free text' idiom symmetrically.
        if self.division == DIVISION_OTHERS:
            if not self.division_other or not str(self.division_other).strip():
                raise ValueError(
                    f"divisionOther is required when division is '{DIVISION_OTHERS}'."
                )
        else:
            # Any non-'others' or None division must have no divisionOther.
            if self.division_other is not None and str(self.division_other).strip():
                raise ValueError(
                    f"divisionOther may only be provided when division is '{DIVISION_OTHERS}'."
                )
        return self


class ActivityCreateRequest(BaseModel):
    """POST /milestones/{milestone_id}/activities.

    Type-specific fields:

    * type='standard':
      - ``status`` (optional; default 'not_completed', one of
        ACTIVITY_STATUS_CHOICES)
      - ``dependency`` (optional; list of any — no referential integrity yet)
      - resourceMode / resourceCount / resource MUST all be omitted.

    * type='resource':
      - resourceMode required (one of 'count' | 'details')
        - 'count'   → provide resourceCount (>=1); resource MUST be omitted
        - 'details' → provide resource (the 9+ fields); resourceCount omitted
      - status / dependency MUST NOT be supplied.

    * type='transactional':
      - Neither the standard-only nor the resource-only fields may be used.
    """
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

    # Standard-only fields.
    status: Optional[str] = Field(
        None,
        description=(
            f"Applies only to type='standard'. One of: "
            f"{', '.join(ACTIVITY_STATUS_CHOICES)}. Defaults to "
            f"'{ACTIVITY_STATUS_DEFAULT}' when omitted."
        ),
    )
    dependency: Optional[List[Any]] = Field(
        None,
        description="Applies only to type='standard'. Reserved; no referential integrity yet.",
    )

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in ACTIVITY_TYPES:
            raise ValueError(
                "Activity type must be one of: standard, resource, transactional."
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

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in ACTIVITY_STATUS_CHOICES:
            raise ValueError(
                f"Activity status must be one of: {', '.join(ACTIVITY_STATUS_CHOICES)}."
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
    def _cross_field_shape(self):
        is_resource_type = self.type == ACTIVITY_TYPE_RESOURCE
        is_standard_type = self.type == ACTIVITY_TYPE_STANDARD

        # status / dependency are STANDARD-only.
        if not is_standard_type:
            if self.status is not None:
                raise ValueError(
                    "status is only valid on standard-type activities."
                )
            if self.dependency is not None:
                raise ValueError(
                    "dependency is only valid on standard-type activities."
                )

        # Resource-block consistency (mirrors prior behaviour; kept verbatim).
        if not is_resource_type:
            if self.resource_mode is not None:
                raise ValueError(
                    "Resource mode should only be provided when the activity type is 'resource'."
                )
            if self.resource_count is not None:
                raise ValueError(
                    "Resource count should only be provided when the activity type is 'resource'."
                )
            if self.resource is not None:
                raise ValueError(
                    "Resource details should only be provided when the activity type is 'resource'."
                )
            return self

        # Resource activity: a mode must be picked.
        if self.resource_mode is None:
            raise ValueError(
                "Please choose a resource mode ('count' or 'details') for a resource-type activity."
            )

        if self.resource_mode == RESOURCE_MODE_COUNT:
            if self.resource_count is None:
                raise ValueError(
                    "Resource count is required when resource mode is 'count'."
                )
            if self.resource is not None:
                raise ValueError(
                    "Resource details should be omitted when resource mode is 'count'."
                )
        else:  # RESOURCE_MODE_DETAILS
            if self.resource is None:
                raise ValueError(
                    "Resource details are required when resource mode is 'details'."
                )
            # typeOfResourceId is mandatory on a details-mode create.
            if not self.resource.type_of_resource_id:
                raise ValueError(
                    "typeOfResourceId is required on the resource block when resource mode is 'details'."
                )
            # division is also mandatory on a details-mode create.
            if self.resource.division is None:
                raise ValueError(
                    "division is required on the resource block when resource mode is 'details'."
                )
            if self.resource_count is not None:
                raise ValueError(
                    "Resource count should be omitted when resource mode is 'details'."
                )
        return self


class ActivityUpdateRequest(BaseModel):
    """PATCH /activities/{id}. Partial; handles type + resource-mode transitions.

    Cross-field consistency (type vs mode vs count vs resource block) is
    enforced in the service layer because a partial update needs the current
    DB state to reason about the final shape.
    """
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
    status: Optional[str] = None
    dependency: Optional[List[Any]] = None

    @field_validator("type", mode="before")
    @classmethod
    def _validate_type(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in ACTIVITY_TYPES:
            raise ValueError(
                "Activity type must be one of: standard, resource, transactional."
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

    @field_validator("status", mode="before")
    @classmethod
    def _validate_status(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip().lower()
        if v not in ACTIVITY_STATUS_CHOICES:
            raise ValueError(
                f"Activity status must be one of: {', '.join(ACTIVITY_STATUS_CHOICES)}."
            )
        return v


class ActivityListQuery(BaseModel):
    offset: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=100)
    includeDeleted: bool = Field(False)
