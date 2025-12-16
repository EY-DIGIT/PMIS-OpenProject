"""
Project API schemas (request/response models).
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


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


class ProjectUpdateRequest(BaseModel):
    """Request schema for updating a project."""
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    active: Optional[bool] = None
    public: Optional[bool] = None
    statusExplanation: Optional[str] = Field(None, max_length=5000, alias="status_explanation")
    parentId: Optional[int] = Field(None, alias="parent_id")


class ProjectListQuery(BaseModel):
    """Query parameters for listing projects."""

    offset: int = Field(1, ge=1, description="Page number (1-indexed)")
    pageSize: int = Field(20, ge=1, le=100, description="Number of items per page")
    active: Optional[bool] = Field(None, description="Filter by active status")
    public: Optional[bool] = Field(None, description="Filter by public status")
