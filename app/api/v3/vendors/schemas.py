"""Vendor request/response schemas."""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class VendorCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: bool = Field(True)


class VendorUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: Optional[bool] = None
