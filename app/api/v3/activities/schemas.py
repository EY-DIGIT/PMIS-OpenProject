"""Activity API schemas.

Doc 38: ``type`` (standard / resource / transactional) is deprecated.
A single ``ActivityCreateRequest`` covers create — name, description,
dates, plus the three new optional ownership/partner fields
``ownerDivision`` / ``concernedDivision`` / ``vendorId``. Status,
dependsOn, resource_mode/count/resource block, and actual dates remain
on the UPDATE path.

The four legacy type-specific create schemas
(StandardActivityCreateRequest etc.) are gone. The single endpoint is
``POST /milestones/{id}/activities/create``. Existing legacy rows in
the activities table keep their ``type`` value; new rows store NULL.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....shared.datetime import IstCalendarDate
from ....domain.activities.activity import (
    ACTIVITY_STATUS_CHOICES,
    ACTIVITY_TYPES,
    RESOURCE_MODES,
)
from ....domain.resource_types.resource_type import DIVISION_CHOICES, DIVISION_OTHERS


class ResourcePayload(BaseModel):
    """Resource block (legacy details-mode shape).

    Doc 38: rarely used now (resource activities deprecated). Kept for
    PATCH compatibility against legacy rows.
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
    type_of_resource_id: Optional[str] = Field(None, alias="typeOfResourceId")
    division: Optional[str] = Field(None)
    division_other: Optional[str] = Field(None, alias="divisionOther", max_length=255)

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
        if self.division == DIVISION_OTHERS:
            if not self.division_other or not str(self.division_other).strip():
                raise ValueError(
                    f"divisionOther is required when division is '{DIVISION_OTHERS}'."
                )
        else:
            if self.division_other is not None and str(self.division_other).strip():
                raise ValueError(
                    f"divisionOther may only be provided when division is '{DIVISION_OTHERS}'."
                )
        return self


class ActivityCreateRequest(BaseModel):
    """POST /milestones/{milestone_id}/activities/create.

    Doc 38 minimal shape: name + description + dates + ownership
    fields. ``status`` / ``dependsOn`` / ``resource*`` / actual dates
    are NOT accepted here — they belong on PATCH.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    # Doc 29: IstCalendarDate normalization.
    start_date: IstCalendarDate = Field(..., alias="startDate")
    end_date: IstCalendarDate = Field(..., alias="endDate")
    position: Optional[int] = Field(None, ge=0)

    # Doc 38: optional ownership / partner / consulted-division fields.
    # Both division fields reference the divisions catalog (codes
    # tmd1 / tmd2 / others). vendorId references vendors.id (typically
    # one of the project's vendors, but not enforced server-side).
    owner_division: Optional[str] = Field(None, alias="ownerDivision")
    concerned_division: Optional[str] = Field(None, alias="concernedDivision")
    vendor_id: Optional[str] = Field(None, alias="vendorId")

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v, info):
        s = info.data.get("start_date")
        if s is not None and v < s:
            raise ValueError("End date cannot be before the start date.")
        return v


class ActivityUpdateRequest(BaseModel):
    """PATCH /activities/{id}. Partial update; all fields optional.

    Doc 38: adds ``ownerDivision`` / ``concernedDivision`` / ``vendorId``.
    The legacy ``type`` / ``resourceMode`` / ``resourceCount`` / ``resource``
    fields stay accepted for back-compat with rows that still carry them.

    ``dependsOn`` semantics: None = no change, [] = clear, [...] = replace.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    type: Optional[str] = None
    # Doc 29: IstCalendarDate normalization.
    start_date: Optional[IstCalendarDate] = Field(None, alias="startDate")
    end_date: Optional[IstCalendarDate] = Field(None, alias="endDate")
    actual_start_date: Optional[IstCalendarDate] = Field(None, alias="actualStartDate")
    actual_end_date: Optional[IstCalendarDate] = Field(None, alias="actualEndDate")
    position: Optional[int] = Field(None, ge=0)
    resource_mode: Optional[str] = Field(None, alias="resourceMode")
    resource_count: Optional[int] = Field(None, ge=1, alias="resourceCount")
    resource: Optional[ResourcePayload] = None
    status: Optional[str] = None
    depends_on: Optional[List[str]] = Field(None, alias="dependsOn")

    # Doc 38 additions.
    owner_division: Optional[str] = Field(None, alias="ownerDivision")
    concerned_division: Optional[str] = Field(None, alias="concernedDivision")
    vendor_id: Optional[str] = Field(None, alias="vendorId")

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
