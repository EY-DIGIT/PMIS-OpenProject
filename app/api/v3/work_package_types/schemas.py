"""
Work Package Type API schemas.
"""
from typing import Optional
from pydantic import BaseModel, Field


class WorkPackageTypeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    internalName: str = Field(..., min_length=1, max_length=100)
    isBuiltin: Optional[bool] = False
    isActive: Optional[bool] = True
    position: Optional[int] = 0


class WorkPackageTypeUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    isActive: Optional[bool] = None
    position: Optional[int] = None


class WorkPackageTypeListQuery(BaseModel):
    offset: int = Field(1, ge=1)
    pageSize: int = Field(20, ge=1, le=100)
